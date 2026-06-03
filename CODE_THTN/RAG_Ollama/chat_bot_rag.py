"""
chat_bot_rag.py
===============
Pipeline gọn, tối ưu tốc độ:

  Câu hỏi
    → [Bước 1] Function Calling: LLM phân loại ý định
                "search_product" | "search_policy" | "answer_direct"
    → [Bước 2] Dense Search: BGE-M3 embed + Milvus COSINE search
    → [Bước 3] LLM trả lời dựa trên context

Đã bỏ: BM25, Re-ranker, Query Rewriting (giảm ~3-5s mỗi lượt)
Ưu tiên: chính xác trước, tốc độ sau

Yêu cầu:
  pip install pymilvus requests
  ollama serve + ollama pull bge-m3 + ollama pull gemma2:9b
  Milvus đang chạy port 19530
  Đã chạy task2_embed_and_insert.py
"""

import json
import os
import requests
import time
from pymilvus import MilvusClient

# ─────────────────────────────────────────────────────────────
# CẤU HÌNH — chỉnh ở đây khi cần
# ─────────────────────────────────────────────────────────────
OLLAMA_URL  = "http://127.0.0.1:11434"
EMBED_MODEL = "bge-m3"       # phải khớp với model dùng lúc insert
VECTOR_DIM  = 1024
LLM_MODEL   = "gemma2:2b"    # 9đổi thành gemma2:2b nếu máy yếu


MILVUS_URI      = "http://localhost:19530"
COLLECTION_NAME = "furniture_rag"

TOP_K_PRODUCT = 5    # lấy top 5 sản phẩm liên quan nhất
TOP_K_POLICY  = 8    # lấy top 8 chunk chính sách
EF_SEARCH     = 150  # độ sâu HNSW: 150 cân bằng speed/accuracy

MIN_SCORE_PRODUCT = 0.55  # ngưỡng cosine cho sản phẩm
MIN_SCORE_POLICY  = 0.50  # ngưỡng cosine cho chính sách

MAX_HISTORY = 10   # số lượt hội thoại tối đa giữ trong lịch sử

# Timeout (giây) — gemma2:9b chậm hơn 2b
TIMEOUT_CLASSIFY = 20   # phân loại câu hỏi
TIMEOUT_LLM      = 300  # sinh câu trả lời


# ═════════════════════════════════════════════════════════════
# EMBEDDING — BGE-M3 qua Ollama REST API
# ═════════════════════════════════════════════════════════════

def embed(text: str) -> list[float]:
    """
    Chuyển text thành vector 1024 chiều qua BGE-M3 Ollama.
    BGE-M3 đã normalize sẵn → dùng trực tiếp với COSINE metric.
    """
    resp = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": [text]},
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    # Ollama trả về "embeddings" (mới) hoặc "embedding" (cũ)
    if "embeddings" in data:
        return data["embeddings"][0]
    return data["embedding"]


# ═════════════════════════════════════════════════════════════
# KHỞI TẠO — kiểm tra kết nối trước khi chat
# ═════════════════════════════════════════════════════════════

def init_services() -> MilvusClient:
    """Kiểm tra Ollama embed + kết nối Milvus. Trả về MilvusClient."""

    # Test embed
    print(f"[Init] Kiểm tra Ollama embed ({EMBED_MODEL})...")
    try:
        vec = embed("test")
        assert len(vec) == VECTOR_DIM, f"Dim sai: {len(vec)} != {VECTOR_DIM}"
        print(f"[Init] Embed OK (dim={len(vec)})")
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Không kết nối Ollama! Chạy: ollama serve")

    # Test LLM có sẵn chưa
    print(f"[Init] Kiểm tra LLM ({LLM_MODEL})...")
    try:
        tags   = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5).json()
        models = [m["name"] for m in tags.get("models", [])]
        if any(LLM_MODEL in m for m in models):
            print(f"[Init] LLM OK")
        else:
            print(f"[Init] CẢNH BÁO: {LLM_MODEL} chưa pull! Chạy: ollama pull {LLM_MODEL}")
    except Exception:
        print(f"[Init] Không kiểm tra được LLM list")

    # Milvus
    print(f"[Init] Kết nối Milvus {MILVUS_URI}...")
    client = MilvusClient(uri=MILVUS_URI)
    client.load_collection(COLLECTION_NAME)  # nạp vào RAM để search nhanh
    print(f"[Init] Milvus OK\n")
    return client


# ═════════════════════════════════════════════════════════════
# BƯỚC 1: FUNCTION CALLING — phân loại ý định câu hỏi
# ═════════════════════════════════════════════════════════════
# Prompt ngắn gọn, rõ ràng → LLM phân loại nhanh và chính xác hơn
CLASSIFY_PROMPT = """Tôi có một câu hỏi, bạn phân tích câu hỏi và phân loại nó vào một trong ba loại:
- search_product : tư vấn, tìm kiếm sản phẩm, hỏi về giá, chất liệu, kích thước
- search_policy  : hỏi về bảo hành, đổi trả, vận chuyển, chính sách, quy định, thông tin liên hệ, thời gian hoạt động mở cửa hoặc đóng cửa
- answer_direct  : chào hỏi thông thường, những phép tính... ngoài những ý search_product và search_policy

Chỉ trả về đúng tên loại, không thêm gì khác.

Câu hỏi: {query}
Loại:"""


def classify_intent(query: str) -> str:
    """
    Dùng LLM phân loại ý định câu hỏi.
    Trả về: "search_product" | "search_policy" | "answer_direct"
    Fallback về "search_product" nếu LLM fail hoặc timeout.
    """
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":  LLM_MODEL,
                "prompt": CLASSIFY_PROMPT.format(query=query),
                "stream": False, # không cần stream vì response rất ngắn, và muốn có timeout chính xác hơn.
                # Giới hạn token output → phân loại nhanh hơn
                "options": {"num_predict": 10, "temperature": 0} # num_predict=10 để đảm bảo LLM chỉ trả về 1 từ loại, không thêm giải thích gì khác, và giảm thời gian xử lý. Temperature=0 để phân loại ổn định hơn.
            },
            timeout=TIMEOUT_CLASSIFY
        )
        resp.raise_for_status()
        result = resp.json().get("response", "").strip().lower()

        # Match kết quả trả về vào tên chuẩn
        if "policy" in result or "chính sách" in result or "bảo hành" in result:
            return "search_policy"
        if "direct" in result or "chào" in result:
            return "answer_direct"
        return "search_product"

    except requests.exceptions.Timeout:
        print(f"  [Classify] Timeout → fallback search_product")
    except Exception as e:
        print(f"  [Classify] Lỗi: {e} → fallback search_product")

    return "search_product"


# ═════════════════════════════════════════════════════════════
# BƯỚC 2: DENSE SEARCH — tìm kiếm ngữ nghĩa trong Milvus
# ═════════════════════════════════════════════════════════════
def search_product(query: str, client: MilvusClient) -> list[dict]:
    """
    Embed query → search Milvus cosine → trả về top K sản phẩm.
    Metadata lưu sẵn trong Milvus → lấy trực tiếp, không parse raw_text.
    """
    qvec = embed(query)
    hits = client.search(
        collection_name=COLLECTION_NAME,
        data=[qvec],
        filter='content_type == "product"',
        limit=TOP_K_PRODUCT,
        output_fields=["metadata_json"],
        search_params={"metric_type": "COSINE", "params": {"ef": EF_SEARCH}}
    )
    results = []
    for hit in hits[0]:
        if hit["distance"] < MIN_SCORE_PRODUCT:
            continue  # loại chunk quá xa về ngữ nghĩa
        meta = json.loads(hit["entity"]["metadata_json"]) # metadata đã lưu sẵn khi insert, không phải parse raw_text → nhanh hơn và chính xác hơn
        results.append({
            "score":    round(hit["distance"], 3), # điểm cosine đã normalize sẵn, chỉ cần round 3 chữ số - để dễ đọc, không cần hiển thị nhiều hơn
            #"raw_text": hit["entity"]["raw_text"],
            "metadata": meta,
        })
    return results


def search_policy(query: str, client: MilvusClient) -> list[dict]:
    """Tìm chunk chính sách liên quan đến câu hỏi."""
    qvec = embed(query)
    hits = client.search(
        collection_name=COLLECTION_NAME,
        data=[qvec],
        filter='content_type == "policy"',
        limit=TOP_K_POLICY,
        output_fields=["raw_text", "metadata_json"],
        search_params={"metric_type": "COSINE", "params": {"ef": EF_SEARCH}}
    )
    results = []
    for hit in hits[0]:
        if hit["distance"] < MIN_SCORE_POLICY:
            continue
        meta = json.loads(hit["entity"]["metadata_json"])
        results.append({
            "score":    round(hit["distance"], 3),
            "text":     hit["entity"]["raw_text"],
            "source":   meta.get("source", ""),
            "section":  meta.get("section", ""),
        })
    return results


# ═════════════════════════════════════════════════════════════
# BUILD CONTEXT — format dữ liệu cho LLM đọc
# ═════════════════════════════════════════════════════════════
def build_product_context(docs: list[dict]) -> str:
    """
    Format sản phẩm thành context có cấu trúc rõ ràng.
    Lấy giá/chất liệu/kích thước từ metadata (đã lưu khi insert)
    thay vì parse raw_text → nhanh hơn và chính xác hơn.
    """
    if not docs:
        return ""

    lines = [f"=== CÓ {len(docs)} SẢN PHẨM LIÊN QUAN ==="]
    for i, doc in enumerate(docs, 1):
        meta = doc["metadata"]
        lines.append(f"\n[SP{i}] {meta.get('name', '')}")
        lines.append(f"  Danh mục  : {meta.get('category', '')}")

        # Format giá và % giảm
        ps = meta.get("price_sale", 0) # giá sale, nếu có, để ưu tiên hiển thị giá đang bán hơn là giá gốc
        po = meta.get("price_original", 0) # giá gốc, để tính % giảm nếu có giá sale và giá gốc
        if ps: # nếu có giá sale, mới hiển thị giá và % giảm, vì giá sale là thông tin khách hàng quan tâm nhất, còn giá gốc chỉ để tham khảo nếu có giá sale. Nếu không có giá sale thì không cần hiển thị gì cả, vì khách hàng sẽ không quan tâm đến giá gốc nếu không có giá sale.
            price_str = f"{int(ps):,}đ".replace(",", ".")
            if po and po > ps:
                pct = round((po - ps) / po * 100)
                price_str += f" (giảm {pct}% từ {f'{int(po):,}đ'.replace(',', '.')})"
            lines.append(f"  Giá bán   : {price_str}")

        if meta.get("material"):
            lines.append(f"  Chất liệu : {meta['material']}")
        if meta.get("size"):
            lines.append(f"  Kích thước: {meta['size']}")

        # Ưu điểm từ metadata (summary đã chuẩn hóa sẵn)
        summary = meta.get("summary", "")
        if summary:
            lines.append(f"  Ưu điểm : {summary}") # ưu điểm đã được chuẩn hóa sẵn khi insert, không phải parse raw_text → nhanh hơn và chính xác hơn

    return "\n".join(lines)


def build_policy_context(docs: list[dict]) -> str:
    """Format chunk chính sách, ghi rõ file nguồn để LLM biết đây là thông tin chính thức."""
    if not docs:
        return ""
    lines = ["=== THÔNG TIN CHÍNH SÁCH ==="]
    for j, item in enumerate(docs, 1):
        src = ""
        if item.get("source"):
            src = f"(nguồn: {item['source']}"
            if item.get("section"):
                src += f" | mục: {item['section']}"
            src += ")"
        lines.append(f"\n[CS{j}] {src}")
        lines.append(item["text"])
    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════
# SYSTEM PROMPT — hướng dẫn hành vi LLM
# ═════════════════════════════════════════════════════════════

SYSTEM_RULES = """Bạn là nhân viên tư vấn bán hàng nội thất. Trả lời bằng tiếng Việt, thân thiện và ngắn gọn. nếu thấy khách chào thì chào lại ngay

LUẬT BẮT BUỘC:
1. CHỈ dùng thông tin trong [NGỮ CẢNH]. KHÔNG tự thêm số liệu ngoài.
2. Giá, kích thước, chất liệu: lấy NGUYÊN XI từ không thay đổi [NGỮ CẢNH].
3. KHÔNG đề cập link, hotline, trang web nếu không có trong [NGỮ CẢNH].
4. Nếu có thông tin → trả lời đầy đủ, cụ thể ngay.
5. Nếu không có → nói: "Xin lỗi, tôi chưa có thông tin về vấn đề này."
6. Khi giới thiệu sản phẩm: nêu đủ tên, giá, chất liệu, kích thước, "summary": "Ưu điểm nổi bật".
7. Nhiều sản phẩm: liệt kê TẤT CẢ theo format:

Dạ, cửa hàng có [N] sản phẩm phù hợp:

**1. [Tên SP1]**
- Giá: [giá]
- Chất liệu: [chất liệu]
- Kích thước: [kích thước]
- Ưu điểm: [Ưu điểm nổi bật của sản phẩm này]

**2. [Tên SP2]**
..."""


def build_system_prompt(context: str) -> str: # nếu có context thì thêm, nếu không có thì vẫn phải có phần [NGỮ CẢNH] để LLM biết không có data liên quan
    ctx = f"[NGỮ CẢNH]\n{context}" if context else "[NGỮ CẢNH]\nKhông có dữ liệu liên quan."
    return f"{SYSTEM_RULES}\n\n{ctx}"


# ═════════════════════════════════════════════════════════════
# BƯỚC 3: LLM STREAMING
# ═════════════════════════════════════════════════════════════

def call_llm(messages: list[dict]) -> str:
    """
    Gửi messages tới Ollama /api/chat, stream response ra màn hình.
    Dùng num_ctx=4096 để giảm thời gian xử lý context (mặc định 8192).
    """
    payload = {
        "model":    LLM_MODEL,
        "messages": messages,
        "stream":   True,
        "options":  {
            "num_ctx":     4096,  # giảm context window → nhanh hơn
            "temperature": 0.3,   # ít ngẫu nhiên → ổn định hơn
        }
    }
    full_response = ""
    print("\nAI tư vấn: ", end="", flush=True)

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload, stream=True, timeout=TIMEOUT_LLM
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("\n[LLM] Không kết nối được Ollama!")
        raise
    except requests.exceptions.Timeout:
        print(f"\n[LLM] Timeout {TIMEOUT_LLM}s")
        return ""

    received_any = False
    for line in resp.iter_lines(): # nếu không nhận được gì sau khi timeout, sẽ trả về empty string và in cảnh báo ở phần gọi hàm
        if not line:
            continue
        try: # có thể có dòng không phải JSON (như heartbeat), nên cần try-except để tránh lỗi dừng stream
            chunk = json.loads(line.decode("utf-8"))
            if "message" in chunk:
                content = chunk["message"]["content"]
                print(content, end="", flush=True)
                full_response += content
                received_any  = True
            if chunk.get("done"):
                print("\n")
        except json.JSONDecodeError:
            continue

    if not received_any:
        print(f"\n[LLM] Không nhận được response! Thử: ollama run {LLM_MODEL}")

    return full_response


# ═════════════════════════════════════════════════════════════
# VÒNG LẶP CHAT
# ═════════════════════════════════════════════════════════════

def chat():
    client = init_services() # khởi tạo và kiểm tra kết nối trước khi chat
    history: list[dict] = []  # lịch sử hội thoại {role, content}
    debug   = False

    print("─" * 55)
    print("  CHÀO MỪNG — TƯ VẤN NỘI THẤT AI")
    print(f"  Embed: {EMBED_MODEL} | LLM: {LLM_MODEL}")
    print("─" * 55)
    print("  'q' = thoát  |  'c' = xóa lịch sử  |  'd' = debug")
    print("─" * 55)

    while True:
        print("\n" + "=" * 40)
        user_input = input("Khách hàng: ").strip() # nếu chỉ nhập khoảng trắng thì sẽ yêu cầu nhập lại, tránh gửi câu trống cho LLM

        if not user_input:
            print("Vui lòng nhập câu hỏi.")
            continue
        if user_input.lower() == "q":
            print("AI: Cảm ơn quý khách! Hẹn gặp lại.")
            break
        if user_input.lower() == "c":
            history = []
            print("--- Đã xóa lịch sử ---")
            continue
        if user_input.lower() == "d":
            debug = not debug
            print(f"--- Debug: {'BẬT' if debug else 'TẮT'} ---")
            continue

        t0 = time.time() # đo thời gian tổng để có thể in ra sau cùng, vì mỗi bước đã có in thời gian riêng, nên sẽ biết bước nào tốn nhiều thời gian nhất để tối ưu sau này.

        # ── Bước 1: Phân loại ý định ──────────────────────────
        intent = classify_intent(user_input) # nếu lỗi hoặc timeout sẽ fallback về "search_product" để vẫn có trải nghiệm tìm kiếm sản phẩm, vì đây là ý định phổ biến nhất và cũng là phần quan trọng nhất cần đảm bảo hoạt động ổn định.
        print(f"  [Intent] {intent}  ({time.time()-t0:.1f}s)")

        # ── Bước 2: Search theo intent ─────────────────────────
        context = "" # context mặc định là rỗng, nếu có kết quả search sẽ format lại để build context cho LLM, nếu không có kết quả nào đủ tốt thì vẫn trả về context rỗng, và LLM sẽ trả lời dựa trên kiến thức đã học (nếu có) hoặc nói rằng không có thông tin liên quan.

        if intent == "search_product": # tìm sản phẩm liên quan, lấy thông tin từ metadata đã lưu sẵn trong Milvus để build context nhanh và chính xác hơn, thay vì parse raw_text.
            docs    = search_product(user_input, client)
            context = build_product_context(docs) # format context theo cấu trúc rõ ràng để LLM dễ đọc và trả lời chính xác hơn, thay vì chỉ liệt kê raw_text lộn xộn.
            sp_info = [f"{d['metadata'].get('name','?')[:18]}({d['score']:.2f})" # để debug nhanh tên sản phẩm và điểm số, thay vì hiển thị toàn bộ metadata hoặc raw_text có thể rất dài và lộn xộn.
                       for d in docs]
            print(f"  [Search] {len(docs)}sp {sp_info}  ({time.time()-t0:.1f}s)")

        elif intent == "search_policy": # tìm chunk chính sách liên quan, lấy raw_text để build context vì thông tin chính sách thường nằm trong phần văn bản chi tiết, metadata chỉ có thể giúp biết file nguồn và section để LLM biết đây là thông tin chính thức, nhưng nội dung chi tiết vẫn cần raw_text để đảm bảo LLM có đủ dữ liệu để trả lời chính xác.
            docs    = search_policy(user_input, client)
            context = build_policy_context(docs)
            cs_info = [f"{d['score']:.2f}:{d.get('source','')[:12]}" for d in docs]
            print(f"  [Search] {len(docs)}cs {cs_info}  ({time.time()-t0:.1f}s)")

        # answer_direct: context rỗng, LLM trả lời thẳng

        if debug:
            print("\n" + "-"*40)
            print(context or "(không có context)")
            print("-"*40)

        # ── Bước 3: Gọi LLM ───────────────────────────────────
        messages = (
            [{"role": "system", "content": build_system_prompt(context)}]
            + history
            + [{"role": "user",  "content": user_input}]
        )

        try:
            answer = call_llm(messages)
            if answer:
                # Lưu lịch sử để duy trì ngữ cảnh hội thoại
                history.append({"role": "user",      "content": user_input})
                history.append({"role": "assistant",  "content": answer})
                # Giới hạn history để tránh context quá dài
                if len(history) > MAX_HISTORY * 2:
                    history = history[-(MAX_HISTORY * 2):]

        except requests.exceptions.ConnectionError:
            print("Hãy chạy 'ollama serve'.")
            break
        except Exception as e:
            print(f"\nLỖI: {e}")
            break

        print(f"  [Tổng] {time.time()-t0:.1f}s")


if __name__ == "__main__":
    chat()