"""
chat_bot_rag.py  —  BGE-M3 via Ollama + Milvus
===============================================
Pipeline:
  Câu hỏi khách
    → Query Enrichment (gộp lịch sử gần nhất)
    → BGE-M3 embed qua Ollama /api/embed
    → Milvus COSINE search (product + policy riêng)
    → Lọc sản phẩm theo dynamic gap
    → Build context có cấu trúc
    → gemma2:2b trả lời dựa trên context

Yêu cầu:
  ollama serve  (đang chạy)
  ollama pull bge-m3
  ollama pull gemma2:2b  (hoặc gemma2:9b)
  Milvus đang chạy port 19530
  Đã chạy task2_embed_and_insert.py
"""

import json
import requests
import os
from collections import defaultdict
from pymilvus import MilvusClient


# ─────────────────────────────────────────────────────────────
# CẤU HÌNH
# ─────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))

OLLAMA_URL      = "http://127.0.0.1:11434"
EMBED_MODEL     = "bge-m3"      # phải khớp với model dùng lúc insert
LLM_MODEL       = "gemma2:2b"   # đổi thành gemma2:9b khi đã cài
VECTOR_DIM      = 1024          # BGE-M3 output dimension

MILVUS_URI      = "http://localhost:19530"
COLLECTION_NAME = "furniture_rag"

TOP_K_PRODUCT = 20   # lấy nhiều để đủ dữ liệu cho bước lọc gap động
TOP_K_POLICY  = 4    # đủ chunk chính sách cho hầu hết câu hỏi
EF_SEARCH     = 200  # độ sâu HNSW search — cao hơn = chính xác hơn, chậm hơn

# Score thresholds — tuned theo BGE-M3 trên dữ liệu nội thất tiếng Việt
MIN_SCORE_PRODUCT = 0.60
MIN_SCORE_POLICY  = 0.55

MAX_PRODUCTS   = 5    # số sp tối đa đưa vào context sau khi lọc gap
DESC_MAX_CHARS = 400  # giới hạn ký tự phần mô tả sp

MAX_HISTORY_TURNS      = 10  # số lượt hội thoại tối đa giữ trong lịch sử
QUERY_ENRICHMENT_TURNS = 2   # số lượt user gần nhất dùng để enrich query


# ═════════════════════════════════════════════════════════════
# EMBEDDING
# ═════════════════════════════════════════════════════════════

def embed_query(text: str) -> list[float]:
    """
    Embed 1 text query thành vector 1024 chiều qua BGE-M3 trên Ollama.
    BGE-M3 qua Ollama đã normalize vector — dùng trực tiếp với COSINE.
    Xử lý 2 dạng response tùy version Ollama:
      "embeddings": [[...]]  (mới) hoặc  "embedding": [...]  (cũ)
    """
    payload  = {"model": EMBED_MODEL, "input": [text]}
    response = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json=payload,
        timeout=30
    )
    response.raise_for_status() # nếu lỗi kết nối hoặc Ollama trả về lỗi HTTP
    data = response.json()

    if "embeddings" in data:
        return data["embeddings"][0] # vì input là list có 1 phần tử, output cũng là list có 1 vector
    elif "embedding" in data:
        return data["embedding"] # một số version Ollama trả về embedding trực tiếp không nằm trong list
    raise ValueError(f"Ollama không trả về embedding: {list(data.keys())}")


# ═════════════════════════════════════════════════════════════
# KHỞI TẠO
# ═════════════════════════════════════════════════════════════

def init_services() -> MilvusClient:
    """
    Kiểm tra Ollama embed + kết nối Milvus.
    Không load model Python vào RAM — BGE-M3 chạy trong Ollama process.
    """
    print(f"[Khởi động] Kiểm tra Ollama embed ({EMBED_MODEL})...")
    try:
        vec = embed_query("test kết nối") # test thoi
        if len(vec) != VECTOR_DIM: # check vector dim đúng cấu hình chưa
            raise ValueError(f"Vector dim thực tế {len(vec)} != cấu hình {VECTOR_DIM}.")
        print(f"[Khởi động] Ollama embed OK (dim={len(vec)})")
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Không kết nối Ollama! Chạy: ollama serve")

    print(f"[Khởi động] Kết nối Milvus {MILVUS_URI}...")
    client = MilvusClient(uri=MILVUS_URI)
    client.load_collection(COLLECTION_NAME) # load collection vào RAM để search nhanh hơn
    print(f"[Khởi động] Sẵn sàng! LLM={LLM_MODEL}, Embed={EMBED_MODEL}\n")
    return client


# ═════════════════════════════════════════════════════════════
# QUERY ENRICHMENT
# ═════════════════════════════════════════════════════════════

def build_enriched_query(user_input: str, history: list[dict]) -> str:
    """
    Gộp N lượt user gần nhất + câu hỏi hiện tại thành 1 chuỗi để embed.
    Giải quyết vấn đề đại từ mơ hồ:
      "bàn ăn moho oslo 901" | "kích thước như thế nào?"
      → vector biết đây là hỏi kích thước của oslo 901.
    Chỉ lấy QUERY_ENRICHMENT_TURNS lượt để tránh nhiễu khi đổi chủ đề.  

    history có dạng
        [
        user,
        assistant,
        user,
        assistant
        ] nên * 2 để lấy đủ lượt user. Nếu không có lịch sử thì trả về nguyên câu hỏi gốc.
    """
    if not history:
        return user_input
    recent     = history[-(QUERY_ENRICHMENT_TURNS * 2):]
    user_turns = [m["content"] for m in recent if m["role"] == "user"]
    return " | ".join(user_turns + [user_input]) if user_turns else user_input # nếu không có lượt user nào trong recent thì vẫn trả về câu hỏi gốc


# ═════════════════════════════════════════════════════════════
# SEARCH MILVUS
# ═════════════════════════════════════════════════════════════

def calc_dynamic_gap(best_score: float) -> float: 
    """
    Gap threshold tự động theo best_score — tuned cho BGE-M3:
      > 0.88 → 0.05: query rõ (tên sp cụ thể), chỉ lấy sp khớp nhất
      > 0.75 → 0.08: query bình thường
      ≤ 0.75 → 0.12: query mơ hồ, lấy rộng hơn để không bỏ sót
    """
    if best_score > 0.88:
        return 0.05
    if best_score > 0.75:
        return 0.08
    return 0.12

def retrieve_context(query_for_embed: str, client: MilvusClient) -> dict:
    """
    Embed query → search Milvus → nhóm sp theo product_id → lọc dynamic gap.
    Policy chunk trả về trực tiếp theo MIN_SCORE mà không lọc thêm.

    {
    "products": [ { "meta": {...}, "chunks": [...], "max_score": 0.9 }, ... ],
    "policies": [ { "text": "...", "source": "...", "section": "..." }, ... ]
    }
    """
    query_vector  = embed_query(query_for_embed)
    results       = {"products": [], "policies": []}
    search_params = {"metric_type": "COSINE", "params": {"ef": EF_SEARCH}}

    # ── Sản phẩm ──────────────────────────────────────────────
    product_hits = client.search(
        collection_name=COLLECTION_NAME,
        data=[query_vector],
        filter='content_type == "product"',
        limit=TOP_K_PRODUCT,
        output_fields=["raw_text", "metadata_json", "chunk_type"],
        search_params=search_params
    )

    # Nhóm chunk theo product_id để tổng hợp đầy đủ thông tin 1 sản phẩm
    # (mỗi sp có 4 chunk: name_only, identity_price, physical, description)
    product_groups = defaultdict(lambda: {
        "meta": {}, 
        "chunks": [], 
        "max_score": 0.0
        }
    ) 

    for hit in product_hits[0]: # vì input là list có 1 phần tử, output cũng là list có 1 list hits
        score = hit["distance"] # COSINE similarity đã normalize về [0,1]
        if score < MIN_SCORE_PRODUCT: # nếu dưới ngưỡng thì bỏ qua luôn, không cần nhóm nữa
            continue  # Nếu điểm dưới 0.6, vứt luôn, không cho vào nhóm.

        meta = json.loads(hit["entity"]["metadata_json"]) # metadata_json chứa thông tin chung của sản phẩm, giống nhau ở tất cả chunk của cùng 1 sp, nên chỉ cần lấy từ 1 chunk nào đó là đủ. Quan trọng nhất là product_id để nhóm chunk đúng sp với nhau.
        pid  = meta.get("product_id", "unknown") # nếu không có product_id thì nhóm vào "unknown", nhưng lý tưởng là dữ liệu đã phải có product_id
        product_groups[pid]["meta"] = meta # cập nhật metadata chung cho nhóm sản phẩm (cùng pid sẽ ghi đè nhau nhưng vì giống nhau nên không vấn đề gì)
        product_groups[pid]["chunks"].append({ # lưu chunk vào nhóm sản phẩm
            "chunk_type": hit["entity"]["chunk_type"], # loại chunk để sau này build context, ví dụ "name_only", "identity_price", "physical", "description"
            "raw_text":   hit["entity"]["raw_text"], # nội dung chunk, ví dụ "Sản phẩm: Bàn Oslo 901", "Từ khóa: bàn ăn, oslo, 901 | Giá bán: 5 triệu", "Chất liệu: gỗ sồi | Kích thước: 120x80cm", hoặc mô tả dài hơn ở chunk description
            "score":      round(score, 4) # Lưu score cao nhất của sản phẩm.
        })
        if score > product_groups[pid]["max_score"]: # cập nhật max_score của nhóm sản phẩm nếu chunk này có score cao hơn
            product_groups[pid]["max_score"] = score # điểm cao nhất trong tất cả chunk của sản phẩm này, dùng để lọc gap động sau khi nhóm xong

    if product_groups: # nếu có sản phẩm nào vượt ngưỡng thì mới tiến hành lọc gap, nếu không có sản phẩm nào thì trả về list rỗng luôn
        sorted_groups = sorted( # sắp xếp nhóm sản phẩm theo max_score giảm dần để nhóm có điểm cao nhất đứng đầu
            product_groups.values(), # lấy giá trị của dict (bỏ qua key là product_id) rồi sắp xếp
            key=lambda x: x["max_score"], reverse=True # sắp xếp giảm dần theo max_score để nhóm có điểm cao nhất đứng đầu
        )
        best_score = sorted_groups[0]["max_score"] # Lấy điểm của thằng đứng đầu (thằng giống nhất)
        gap        = calc_dynamic_gap(best_score)
        # Chỉ giữ sp trong vòng `gap` điểm của sp tốt nhất
        filtered = [g for g in sorted_groups
                    if g["max_score"] >= best_score - gap] #  Điểm cao -> Khắt khe (lấy ít); Điểm thấp -> Nới lỏng (lấy rộng).
        results["products"] = filtered[:MAX_PRODUCTS]
        # Nếu bạn hỏi cực kỳ chính xác -> best_score cao -> gap nhỏ -> Vùng an toàn hẹp -> Chỉ lấy 1 sản phẩm.
        # Nếu bạn hỏi mơ hồ -> best_score thấp -> gap rộng -> Vùng an toàn lớn -> Lấy nhiều sản phẩm để gợi ý.'''

    # ── Chính sách ────────────────────────────────────────────
    policy_hits = client.search(
        collection_name=COLLECTION_NAME,
        data=[query_vector],
        filter='content_type == "policy"',
        limit=TOP_K_POLICY,
        output_fields=["raw_text", "metadata_json"],
        search_params=search_params
    )

    for hit in policy_hits[0]: # vì input là list có 1 phần tử, output cũng là list có 1 list hits
        score = hit["distance"]
        if score >= MIN_SCORE_POLICY: # CHỐT CHẶN: Chỉ lấy nếu điểm > 0.55
            meta = json.loads(hit["entity"]["metadata_json"])
            results["policies"].append({
                "text":    hit["entity"]["raw_text"],
                "score":   round(score, 3),
                "source":  meta.get("source", ""),
                "section": meta.get("section", ""),
            })

    return results

# ═════════════════════════════════════════════════════════════
# PARSE CHUNK → THÔNG TIN SẢN PHẨM
# ═════════════════════════════════════════════════════════════

def parse_pipe_attrs(raw_text: str) -> dict:
    """
    Parse chuỗi pipe-separated thành dict.
    "Sản phẩm: X | Chất liệu: Y | Kích thước: Z"
    → {"Sản phẩm": "X", "Chất liệu": "Y", "Kích thước": "Z"}
    """
    attrs = {}
    for part in raw_text.split(" | "): # tách theo " | " để lấy từng cặp key-value, sau đó tách tiếp theo ":"
        part = part.strip() # loại bỏ khoảng trắng thừa ở đầu và cuối phần tử
        if ":" in part:# nếu có dấu ":" thì mới tách thành key-value, nếu không có thì bỏ qua phần tử này vì không đúng định dạng
            key, _, val = part.partition(":") # partition sẽ tách chuỗi thành 3 phần: phần trước dấu ":", dấu ":", và phần sau dấu ":". Nếu có nhiều dấu ":" thì chỉ tách ở dấu đầu tiên, phần sau sẽ nguyên vẹn. Ví dụ "Từ khóa: bàn ăn: oslo" sẽ được tách thành key="Từ khóa", val="bàn ăn: oslo"
            attrs[key.strip()] = val.strip()
    return attrs


def build_product_info(group: dict) -> dict:
    """
    Tổng hợp thông tin sp từ tất cả chunk của nhóm.
    Phân nhánh theo chunk_type — không detect từ nội dung raw_text:
      name_only      → bỏ qua (chỉ dùng để search)
      identity_price → tags, giá bán
      physical       → chất liệu, kích thước
      description    → mô tả đầy đủ (phần sau dòng "Sản phẩm: ...")
    """
    info = { # bắt đầu với thông tin cơ bản từ metadata, sau đó sẽ cập nhật thêm từ chunk
        "name": group["meta"].get("name", ""),
        "category": group["meta"].get("category", ""),
        "tags": "", "price": "", "material": "", "size": "", "description": "",
    }
    for chunk in group["chunks"]: # duyệt qua tất cả chunk của nhóm sản phẩm để tổng hợp thông tin
        ctype, raw = chunk["chunk_type"], chunk["raw_text"] 
        if ctype == "name_only": # chunk name_only chỉ dùng để search, không chứa thông tin gì mới so với metadata đã có, nên bỏ qua không cần parse thêm, vì info["name"] đã được lấy từ metadata rồi. Nếu sau này có chunk nào khác cũng chứa tên sản phẩm thì sẽ cập nhật vào info["name"] nếu muốn, nhưng hiện tại theo cấu trúc dữ liệu thì chỉ có metadata mới chứa tên đầy đủ của sản phẩm.
            pass
        elif ctype == "identity_price": # chunk này chứa thông tin về tags và giá bán, được định dạng theo kiểu "Từ khóa: ... | Giá bán: ..." nên sẽ parse theo cấu trúc pipe-separated để lấy ra từng phần thông tin một cách linh hoạt, tránh phụ thuộc vào thứ tự của các phần thông tin trong chuỗi raw_text.
            attrs = parse_pipe_attrs(raw)
            info["tags"]  = attrs.get("Từ khóa", "")
            info["price"] = attrs.get("Giá bán", "")
        elif ctype == "physical":
            attrs = parse_pipe_attrs(raw)
            info["material"] = attrs.get("Chất liệu", "")
            info["size"]     = attrs.get("Kích thước", "")
        elif ctype == "description":
            # "Sản phẩm: X\n<mô tả>" → bỏ dòng đầu, lấy mô tả
            if "\n" in raw: # nếu có dòng mới thì mới tách, nếu không có dòng mới thì phần mô tả sẽ để trống vì không đúng định dạng
                parts = raw.split("\n", 1)
                info["description"] = parts[1].strip() if len(parts) > 1 else ""
    return info


# ═════════════════════════════════════════════════════════════
# BUILD CONTEXT BLOCK
# ═════════════════════════════════════════════════════════════
# Context (Ngữ cảnh): "Cuốn sách tra cứu" sau khi đã tìm kiếm trong Milvus.
# Vai trò: Cung cấp kiến thức thực tế (Giá cả, chất liệu, chính sách).
# Kết hợp: Hàm build_system_prompt(context_block) sẽ dán nội dung này ngay bên dưới SYSTEM_RULES.
def build_context_block(retrieved: dict) -> str:
    """
    Format kết quả search thành context có cấu trúc cho LLM.
    Header "CÓ N SẢN PHẨM" báo LLM biết cần liệt kê đủ bao nhiêu sp.
    Chính sách kèm tên file nguồn để LLM biết đây là thông tin chính thức.
    """
    blocks = []

    if retrieved["products"]:
        n = len(retrieved["products"]) #
        blocks.append(f"=== CÓ {n} SẢN PHẨM LIÊN QUAN ===") # header này rất quan trọng để LLM biết cần giới thiệu đủ N sản phẩm, tránh tình trạng chỉ giới thiệu 1 sp dù có nhiều sp phù hợp trong ngữ cảnh
        for i, group in enumerate(retrieved["products"], 1):
            info  = build_product_info(group)
            lines = [f"\n[SP{i}] {info['name']}"]
            if info["category"]: lines.append(f"  Danh mục  : {info['category']}")
            if info["tags"]:     lines.append(f"  Từ khóa   : {info['tags']}")
            if info["price"]:    lines.append(f"  Giá bán   : {info['price']}")
            if info["material"]: lines.append(f"  Chất liệu : {info['material']}")
            if info["size"]:     lines.append(f"  Kích thước: {info['size']}")
            if info["description"]:
                desc = info["description"]
                if len(desc) > DESC_MAX_CHARS:
                    desc = desc[:DESC_MAX_CHARS] + "..." # cắt mô tả nếu quá dài để tránh ngập context, vì mô tả thường chiếm nhiều ký tự nhất
                lines.append(f"  Mô tả     : {desc}")
            blocks.append("\n".join(lines))

    if retrieved["policies"]:
        blocks.append("\n=== THÔNG TIN CHÍNH SÁCH ===")
        for j, item in enumerate(retrieved["policies"], 1): # đánh số chính sách để LLM dễ tham chiếu, ví dụ "theo chính sách [CS1] thì..."
            src_label = ""
            if item.get("source"):
                src_label = f"(nguồn: {item['source']}"
                if item.get("section"):
                    src_label += f" | mục: {item['section']}"
                src_label += ")"
            blocks.append(f"\n[CS{j}] {src_label}")
            blocks.append(item["text"])

    return "\n".join(blocks) if blocks else ""


# ═════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═════════════════════════════════════════════════════════════
SYSTEM_RULES = """Bạn là nhân viên tư vấn bán hàng nội thất. Trả lời bằng tiếng Việt, thân thiện và ngắn gọn.

LUẬT BẮT BUỘC — vi phạm là sai:
1. CHỈ dùng thông tin trong [NGỮ CẢNH]. KHÔNG tự thêm số liệu ngoài.
2. Giá, kích thước, chất liệu: lấy NGUYÊN XI từ [NGỮ CẢNH], không được thay đổi.
3. Nếu [NGỮ CẢNH] có đủ thông tin → trả lời đầy đủ, cụ thể ngay.
4. Nếu [NGỮ CẢNH] KHÔNG có thông tin → nói: "Xin lỗi, tôi chưa có thông tin về vấn đề này."
5. Khi giới thiệu sản phẩm: PHẢI nêu đủ tên, giá bán, chất liệu, kích thước.
6. [NGỮ CẢNH] có bao nhiêu sản phẩm [SP1],[SP2]...: PHẢI giới thiệu ĐỦ bấy nhiêu.

CÁCH TRÌNH BÀY KHI CÓ NHIỀU SẢN PHẨM:
Dạ, cửa hàng có [N] sản phẩm phù hợp:

**1. [Tên SP1]**
- Giá: [giá]
- Chất liệu: [chất liệu]
- Kích thước: [kích thước]

**2. [Tên SP2]**
- Giá: [giá]
- Chất liệu: [chất liệu]
- Kích thước: [kích thước]"""


# SYSTEM_RULES Nó được gán vào hàm build_system_prompt để làm cái nền móng cho mọi câu trả lời.
def build_system_prompt(context_block: str) -> str: # nếu có ngữ cảnh thì thêm header [NGỮ CẢNH], 
    ctx = (f"[NGỮ CẢNH]\n{context_block}" if context_block
           else "[NGỮ CẢNH]\nKhông có dữ liệu liên quan.") # nếu không có thì vẫn phải có header nhưng ghi rõ "Không có dữ liệu liên quan" để LLM biết là không có ngữ cảnh nào để tham khảo, tránh trường hợp LLM tưởng mình quên đưa ngữ cảnh mà tự nhiên bịa ra thông tin không có thật.
    return f"{SYSTEM_RULES}\n\n{ctx}"


# ═════════════════════════════════════════════════════════════
# OLLAMA LLM STREAMING
# ═════════════════════════════════════════════════════════════

def chat_ollama_llm(messages: list[dict]) -> str:
    """Gửi messages tới Ollama /api/chat, stream response ra màn hình."""
    payload       = {"model": LLM_MODEL, "messages": messages, "stream": True}
    full_response = ""
    print("\nAI tư vấn: ", end="", flush=True)

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload, stream=True, timeout=120
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("\nLỖI: Không kết nối Ollama.")
        raise

    for line in response.iter_lines(): # Đọc từng dòng dữ liệu "chảy" về từ server Ollama
        if line:
            chunk = json.loads(line.decode("utf-8")) # Chuyển dòng dữ liệu thô (bytes) thành đối tượng JSON (Dictionary)
            # Kiểm tra nếu trong gói dữ liệu có chứa nội dung tin nhắn
            if "message" in chunk:
                content = chunk["message"]["content"] # Trích xuất phần chữ AI vừa tạo ra
                print(content, end="", flush=True)
                full_response += content # Lưu lại toàn bộ phản hồi của AI để có thể sử dụng sau này nếu cần, ví dụ để lưu vào lịch sử hội thoại hoặc phân tích thêm
            # Nếu nhận được tín hiệu "done": true từ AI -> Kết thúc câu trả lời
            if chunk.get("done"):
                print("\n")

    return full_response


# ═════════════════════════════════════════════════════════════
# VÒNG LẶP CHAT
# ═════════════════════════════════════════════════════════════

def chat_with_rag():
    milvus_client = init_services()
    conversation_history: list[dict] = []
    debug_mode = False

    print("─" * 55)
    print("  CHÀO MỪNG — TƯ VẤN NỘI THẤT AI")
    print(f"  Embed: {EMBED_MODEL} | LLM: {LLM_MODEL}")
    print("─" * 55)
    print("  'q' = thoát  |  'c' = xóa lịch sử  |  'd' = debug")
    print("─" * 55)

    while True:
        print("\n" + "=" * 40)
        user_input = input("Khách hàng: ").strip()

        if user_input.lower() == "q":
            print("AI: Cảm ơn quý khách! Hẹn gặp lại.")
            break
        if user_input.lower() == "c":
            conversation_history = []
            print("--- Đã xóa lịch sử ---")
            continue
        if user_input.lower() == "d":
            debug_mode = not debug_mode
            print(f"--- Debug: {'BẬT' if debug_mode else 'TẮT'} ---")
            continue
        if not user_input: # nếu khách hàng chỉ nhấn Enter mà không nhập gì thì bỏ qua, không gọi LLM, tránh tạo phản hồi vô nghĩa hoặc lỗi do input rỗng
            continue

        # 1. Enrich query bằng lịch sử
        query_for_embed = build_enriched_query(user_input, conversation_history)

        # 2. Search Milvus
        try:
            retrieved = retrieve_context(query_for_embed, milvus_client)
        except requests.exceptions.Timeout:
            print("  [Timeout] Ollama embed chậm, thử lại...")
            continue
        except Exception as e:
            print(f"  [Lỗi] {e}")
            continue

        context_block = build_context_block(retrieved)

        # 3. Debug log
        n_prod   = len(retrieved["products"])
        sp_info  = [f"{g['meta'].get('name','?')[:15]}({g['max_score']:.3f})"
                    for g in retrieved["products"]]
        cs_info  = [f"{p['score']:.3f}:{p.get('source','')[:12]}"
                    for p in retrieved["policies"]]
        gap_used = (calc_dynamic_gap(retrieved["products"][0]["max_score"])
                    if retrieved["products"] else 0)

        print(f"  [RAG] {n_prod}sp gap={gap_used} {sp_info}")
        print(f"  [RAG] cs={cs_info}")
        print(f"  [Q]   {query_for_embed[:75]}{'...' if len(query_for_embed)>75 else ''}")

        if debug_mode:
            print("\n" + "-"*40)
            print(context_block)
            print("-"*40)

        # 4. Gọi LLM
        system_prompt = build_system_prompt(context_block)
        messages = ( # Lắp ghép mọi thứ lại thành một mẩu tin gửi đi
            [{"role": "system", "content": system_prompt}] # 1. Luật + Kiến thức
            + conversation_history  # 2. Trí nhớ (các câu hỏi đáp cũ)
            + [{"role": "user",  "content": f"Câu hỏi của khách: {user_input}"}] # 3. Câu hỏi mới
        )

        try:
            ai_response = chat_ollama_llm(messages)
            # Lưu history với nội dung gốc (không có prefix "Câu hỏi của khách:")
            conversation_history.append({"role": "user",      "content": user_input})
            conversation_history.append({"role": "assistant",  "content": ai_response})
            if len(conversation_history) > MAX_HISTORY_TURNS * 2:
                conversation_history = conversation_history[-(MAX_HISTORY_TURNS * 2):]

        except requests.exceptions.ConnectionError:
            print("Hãy chạy 'ollama serve'.")
            break
        except Exception as e:
            print(f"\nLỖI: {e}")
            break


if __name__ == "__main__":
    chat_with_rag()

