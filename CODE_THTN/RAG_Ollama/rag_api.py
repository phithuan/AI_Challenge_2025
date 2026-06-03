"""
rag_api.py
==========
Microservice API cho Chatbot RAG nội thất.

Luồng xử lý:
1. Classify intent bằng câu hỏi hiện tại.
2. Retrieval sản phẩm/chính sách bằng câu hỏi hiện tại.
3. LLM trả lời dựa trên:
   - SYSTEM_RULES
   - context vừa retrieval
   - 1 câu trả lời gần nhất của chatbot trên giao diện
   - câu hỏi hiện tại

Chạy:
    uvicorn rag_api:app --host 127.0.0.1 --port 8010 --reload

Yêu cầu:
    pip install fastapi uvicorn pymilvus requests groq

Cần chạy trước:
    ollama serve
    ollama pull bge-m3

Milvus:
    http://localhost:19530
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI
from groq import Groq
from pydantic import BaseModel
from pymilvus import MilvusClient


# =========================================================
# CẤU HÌNH
# =========================================================

OLLAMA_URL = "http://127.0.0.1:11434"
EMBED_MODEL = "bge-m3"
VECTOR_DIM = 1024

GROQ_MODEL = "llama-3.1-8b-instant"

MILVUS_URI = "http://localhost:19530"
COLLECTION_NAME = "furniture_rag"

TOP_K_PRODUCT = 10
TOP_K_POLICY = 12
EF_SEARCH = 150

MIN_SCORE_PRODUCT = 0.50
MIN_SCORE_POLICY = 0.50

TIMEOUT_EMBED = 60

# Lấy 2 câu trả lời gần nhất của assistant trên giao diện.
# Không dùng history để search, chỉ dùng cho LLM hiểu tham chiếu giao diện.
MAX_LAST_ASSISTANT_MESSAGES = 2
MAX_LAST_ASSISTANT_CHARS_EACH = 1200

# Log preview cho dễ đọc terminal.
LOG_PREVIEW_CHARS = 700 # Giới hạn số ký tự hiển thị trong log để tránh quá dài, vẫn đủ để debug ý tưởng chính của câu trả lời hoặc ngữ cảnh.


# =========================================================
# GROQ CLIENT
# =========================================================

def _load_api_key() -> str:
    key_file = Path(__file__).resolve().parent / "api_key.txt"

    if not key_file.exists():
        raise FileNotFoundError(f"Không tìm thấy: {key_file}")

    key = key_file.read_text(encoding="utf-8").strip()

    if not key:
        raise ValueError("File api_key.txt đang rỗng.")

    return key


groq_client = Groq(api_key=_load_api_key())


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(title="Furniture RAG Chatbot API", version="2.3.1")

milvus_client: Optional[MilvusClient] = None


# =========================================================
# REQUEST / RESPONSE
# =========================================================
class ChatMessage(BaseModel): # Định nghĩa cấu trúc message trong history, gồm role (user hoặc assistant) và content (nội dung tin nhắn)
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: List[ChatMessage] = []


class ChatResponse(BaseModel): # Trả về câu trả lời, intent, số sản phẩm và chính sách tìm được, thời gian xử lý
    answer: str
    intent: str = ""
    product_count: int = 0
    policy_count: int = 0
    elapsed: float = 0.0


# =========================================================
# LOG HELPERS
# =========================================================
def now_str() -> str: # Lấy thời gian hiện tại dưới dạng string để log
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def preview_text(text: str, limit: int = LOG_PREVIEW_CHARS) -> str: # Dùng để cắt bớt text dài khi in log.
    """
    Cắt text dài để log dễ nhìn.
    """
    if not text:
        return "Không có."

    text = text.strip()

    if len(text) <= limit:
        return text

    return text[:limit].rstrip() + "... [truncated]"


def log_section(title: str): # In tiêu đề section để phân tách các phần log, giúp dễ đọc.
    """
    In tiêu đề section, không dùng dấu ===== để tránh rối.
    """
    print(f"\n[{title}]")


def log_key_value(key: str, value: Any): # In cặp key-value để log chi tiết, giúp dễ đọc và thống nhất format log.
    print(f"- {key}: {value}")


def log_chat_end(): # In dấu kết thúc chat để phân tách giữa các request trong log, giúp dễ đọc.
    """
    Chỉ dùng dấu ===== ở cuối mỗi lượt chat theo yêu cầu.
    """
    print("\n==================== END CHAT ====================\n")


# =========================================================
# HISTORY PROCESSING
# =========================================================

def normalize_history(history: List[ChatMessage]) -> List[Dict[str, str]]:
    """
    Làm sạch history từ giao diện.
    History không dùng cho retrieval.
    Chỉ dùng để lấy câu trả lời assistant gần nhất khi gọi LLM.
    """
    clean = []

    for item in history:
        role = item.role.strip().lower()
        content = item.content.strip()

        if role not in ["user", "assistant"]: # chỉ giữ lại message có: role là user hoặc assistant
            continue

        if not content:
            continue

        clean.append({
            "role": role,
            "content": content
        })

    return clean


def get_last_assistant_answers(history: List[Dict[str, str]]) -> str:
    """
    Lấy 2 câu trả lời gần nhất của chatbot trên giao diện.

    Mục đích:
    - Giúp LLM hiểu các câu hỏi tham chiếu:
    - Không dùng history để retrieval/search.
    - Chỉ đưa 2 câu trả lời assistant gần nhất vào system prompt.
    """
    assistant_answers = []

    for msg in reversed(history):
        if msg["role"] == "assistant":
            content = msg["content"][:MAX_LAST_ASSISTANT_CHARS_EACH]
            assistant_answers.append(content)

        if len(assistant_answers) >= MAX_LAST_ASSISTANT_MESSAGES:
            break

    if not assistant_answers:
        return ""

    # Đảo lại để hiển thị theo thứ tự cũ -> mới
    assistant_answers = list(reversed(assistant_answers))

    lines = []

    for i, ans in enumerate(assistant_answers, 1):
        lines.append(f"[Câu trả lời assistant gần nhất #{i}]\n{ans}")

    return "\n\n".join(lines)

# =========================================================
# EMBEDDING
# =========================================================
def embed(text: str) -> List[float]: # Nhận text
    resp = requests.post(
        f"{OLLAMA_URL}/api/embed", # Gọi API embed của Ollama 
        json={
            "model": EMBED_MODEL, # Dùng model embed đã cấu hình
            "input": [text] # Đưa text vào dưới dạng list để embed (có thể embed nhiều câu cùng lúc nếu cần)
        },
        timeout=TIMEOUT_EMBED, # Giới hạn thời gian chờ để tránh treo lâu khi embed
    )

    resp.raise_for_status() # Nếu có lỗi HTTP sẽ ném exception để dễ debug

    data = resp.json()
    vector = data.get("embeddings", [data.get("embedding")])[0]

    if len(vector) != VECTOR_DIM: # Kiểm tra embedding trả về có đúng kích thước mong đợi không
        raise ValueError(f"Embedding dimension sai: {len(vector)} != {VECTOR_DIM}")

    return vector # Trả về vector embedding dưới dạng list float


# =========================================================
# STARTUP
#Khi chạy:
#uvicorn rag_api:app --host 127.0.0.1 --port 8010 --reload
#FastAPI gọi:
# =========================================================
@app.on_event("startup")
def startup_event():
    global milvus_client

    print("[STARTUP] RAG API đang khởi động...")
    print(f"[STARTUP] Embed model: {EMBED_MODEL}")

    test_vec = embed("test") # Test embedding với chữ "test"
    print(f"[STARTUP] Embed OK, dim={len(test_vec)}")

    print(f"[STARTUP] Kết nối Milvus: {MILVUS_URI}") # Nếu embed OK thì kết nối Milvus
    milvus_client = MilvusClient(uri=MILVUS_URI)
    milvus_client.load_collection(COLLECTION_NAME) # Load collection furniture_rag

    print(f"[STARTUP] Collection: {COLLECTION_NAME}")
    print(f"[STARTUP] Groq model: {GROQ_MODEL}")
    print("[STARTUP] Service sẵn sàng nhận câu hỏi.")


# =========================================================
# INTENT CLASSIFICATION
# =========================================================

CLASSIFY_PROMPT = """
Bạn là bộ phân loại intent cho chatbot nội thất.

Hãy phân loại câu hỏi của người dùng vào đúng 1 trong 3 loại sau:

1. search_product
- Dùng khi người dùng muốn tìm, mua, xem sản phẩm cụ thể trong cửa hàng.
- Bao gồm hỏi giá, chất liệu, kích thước, màu sắc, còn hàng của sản phẩm.
- Cũng dùng cho câu hỏi tham chiếu sản phẩm trước đó như:
  "mẫu đầu tiên giá bao nhiêu"
  "mẩu đầu tiên giá bao nhiêu"
  "mẫu thứ 2 chất liệu gì"
  "mẩu thứ 2 chất liệu gì"
  "cái đó có màu trắng không"
  "sản phẩm trên còn hàng không"

Ví dụ:
- "tôi cần mua bàn ăn"
- "có sofa màu xám không"
- "bàn gỗ giá bao nhiêu"
- "tìm ghế văn phòng"
- "mẫu đầu tiên giá bao nhiêu"

2. search_policy
- Dùng khi người dùng hỏi thông tin tư vấn, hướng dẫn, quy định hoặc chính sách.
- Bao gồm: bảo hành, đổi trả, vận chuyển, thanh toán, liên hệ, giờ mở cửa.
- Nếu câu hỏi mang tính tư vấn chọn nội thất theo không gian sống, phong cách, công năng, gia đình, trẻ nhỏ, căn hộ, phòng khách, phòng ngủ, bảo quản, vệ sinh... thì phân loại là search_policy.

Ví dụ:
- "bảo hành bao lâu"
- "có đổi trả không"
- "cửa hàng ở đâu"
- "nhà 40m2 nên chọn nội thất thế nào"
- "phong cách Japandi bắt đầu từ đâu"
- "nhà có trẻ nhỏ nên chọn nội thất thế nào"
- "với mẫu thứ 2 chính sách bảo hành như thế nào"

3. answer_direct
- Dùng cho chào hỏi, cảm ơn, tạm biệt, phép tính đơn giản hoặc câu hỏi ngoài nội thất/chính sách/sản phẩm.

Ví dụ:
- "xin chào"
- "cảm ơn"
- "2 + 3 bằng mấy"
- "thời tiết hôm nay thế nào"

Quy tắc:
- Chỉ dựa vào câu hỏi hiện tại.
- Không cần tự suy luận từ history.
- Chỉ trả về đúng một nhãn: search_product, search_policy, answer_direct.
- Không giải thích.

Câu hỏi: {query}

Loại:
"""


def classify_intent(query: str) -> str:
    """
    Classify chỉ dùng câu hỏi hiện tại.
    Không dùng history để tránh kéo lệch intent.
    """
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": CLASSIFY_PROMPT.format(query=query)
                }
            ],
            temperature=0,
            max_completion_tokens=10,
        )

        result = resp.choices[0].message.content.strip().lower()

        if "search_policy" in result or "policy" in result:
            return "search_policy"

        if "answer_direct" in result or "direct" in result:
            return "answer_direct"

        return "search_product"

    except Exception as e:
        print(f"[ERROR][Classify] {e} -> fallback search_product")
        return "search_product"


# =========================================================
# SEARCH PRODUCT / POLICY
# =========================================================

def search_product(query: str) -> List[Dict[str, Any]]:
    """
    Search sản phẩm bằng chính câu hỏi hiện tại.
    Không dùng history.
    """
    if milvus_client is None:
        raise RuntimeError("Milvus client chưa được khởi tạo.")

    qvec = embed(query)

    hits = milvus_client.search(
        collection_name=COLLECTION_NAME,
        data=[qvec],
        filter='content_type == "product"',
        limit=TOP_K_PRODUCT,
        output_fields=["metadata_json"],
        search_params={
            "metric_type": "COSINE",
            "params": {"ef": EF_SEARCH}
        },
    )

    results = []

    for hit in hits[0]:
        if hit["distance"] < MIN_SCORE_PRODUCT:
            continue

        meta = json.loads(hit["entity"]["metadata_json"])

        results.append({
            "score": round(hit["distance"], 3),
            "metadata": meta
        })

    return results


def search_policy(query: str) -> List[Dict[str, Any]]:
    """
    Search chính sách/tư vấn bằng chính câu hỏi hiện tại.
    Không dùng history.
    """
    if milvus_client is None:
        raise RuntimeError("Milvus client chưa được khởi tạo.")

    qvec = embed(query)

    hits = milvus_client.search(
        collection_name=COLLECTION_NAME,
        data=[qvec],
        filter='content_type == "policy"',
        limit=TOP_K_POLICY,
        output_fields=["raw_text", "metadata_json"],
        search_params={
            "metric_type": "COSINE",
            "params": {"ef": EF_SEARCH}
        },
    )

    results = []

    for hit in hits[0]:
        if hit["distance"] < MIN_SCORE_POLICY:
            continue

        meta = json.loads(hit["entity"]["metadata_json"])

        results.append({
            "score": round(hit["distance"], 3),
            "text": hit["entity"]["raw_text"],
            "source": meta.get("source", ""),
            "section": meta.get("section", ""),
        })

    return results


# =========================================================
# BUILD CONTEXT
# =========================================================

def format_price(value: Any) -> str:
    try:
        return f"{int(float(value)):,}đ".replace(",", ".")
    except Exception:
        return ""


def build_product_context(docs: List[Dict[str, Any]]) -> str:
    if not docs:
        return ""

    lines = [f"=== CÓ {len(docs)} SẢN PHẨM LIÊN QUAN ==="]

    for i, doc in enumerate(docs, 1):
        meta = doc["metadata"]

        product_id = meta.get("product_id", "")
        name = meta.get("name", "")
        category = meta.get("category", "")
        material = meta.get("material", "")
        size = meta.get("size", "")
        summary = meta.get("summary", "")

        price_sale = meta.get("price_sale", 0)
        price_original = meta.get("price_original", 0)

        price_text = format_price(price_sale)

        try:
            if price_original and float(price_original) > float(price_sale):
                pct = round(
                    (float(price_original) - float(price_sale))
                    / float(price_original)
                    * 100
                )
                price_text += f" (giảm {pct}% từ {format_price(price_original)})"
        except Exception:
            pass

        lines.append(f"\n[SP{i}] {name}")
        lines.append(f"  ID_SAN_PHAM: {product_id}")
        lines.append(f"  Link bắt buộc: /product/{product_id}/")

        if category:
            lines.append(f"  Danh mục  : {category}")

        if price_text:
            lines.append(f"  Giá bán   : {price_text}")

        if material:
            lines.append(f"  Chất liệu : {material}")

        if size:
            lines.append(f"  Kích thước: {size}")

        if summary:
            lines.append(f"  Ưu điểm   : {summary}")

    return "\n".join(lines)


def build_policy_context(docs: List[Dict[str, Any]]) -> str:
    if not docs:
        return ""

    lines = ["=== THÔNG TIN CHÍNH SÁCH VÀ TƯ VẤN ==="]

    for doc in docs:
        section = doc.get("section", "Thông tin chung")
        source = doc.get("source", "")
        text = doc.get("text", "")

        lines.append(f"\nCHỦ ĐỀ: {section}")
        lines.append(f"NGUỒN: {source}")
        lines.append(f"NỘI DUNG:\n{text}")
        lines.append("-" * 30)

    return "\n".join(lines)


# =========================================================
# SYSTEM RULES
# =========================================================

SYSTEM_RULES = """
Bạn là nhân viên tư vấn bán hàng nội thất. Trả lời bằng tiếng Việt, thân thiện, rõ ràng.

DỮ LIỆU BẠN ĐƯỢC PHÉP DÙNG:
1. [NGỮ CẢNH] là dữ liệu vừa được truy xuất từ hệ thống RAG.
2. [CÂU TRẢ LỜI TRƯỚC GẦN NHẤT TRÊN GIAO DIỆN] chỉ được dùng để hiểu các câu hỏi tham chiếu như:
   - "mẫu đầu tiên"
   - "mẩu đầu tiên"
   - "mẫu thứ 2"
   - "mẩu thứ 2"
   - "cái đó"
   - "sản phẩm trên"
   - "nó"
   - "mẫu này"

LUẬT BẮT BUỘC:
1. Không được tự bịa sản phẩm, giá, chất liệu, kích thước, chính sách hoặc ID.
2. Ưu tiên trả lời bằng [NGỮ CẢNH] nếu có dữ liệu phù hợp.
3. Nếu [NGỮ CẢNH] không có dữ liệu nhưng [CÂU TRẢ LỜI TRƯỚC GẦN NHẤT TRÊN GIAO DIỆN] có đúng thông tin để trả lời câu hỏi tham chiếu, bạn được phép dùng câu trả lời trước đó để trả lời.
4. Nếu cả [NGỮ CẢNH] và [CÂU TRẢ LỜI TRƯỚC GẦN NHẤT TRÊN GIAO DIỆN] đều không có dữ liệu phù hợp, chỉ trả lời:
   "Xin lỗi, tôi chưa có thông tin về vấn đề này."

ĐỊNH DẠNG TRẢ LỜI SẢN PHẨM:
- Nếu liệt kê nhiều sản phẩm, bắt buộc dùng số thứ tự.
- Nếu có ID_SAN_PHAM, bắt buộc dùng link:
  <a href="/product/[ID_SAN_PHAM]/" class="chatbot-link">[Tên SP]</a>
- Format:
  1. <a href="/product/[ID_SAN_PHAM]/" class="chatbot-link">[Tên SP]</a>
     - Giá: [giá]
     - Chất liệu: [chất liệu]
     - Kích thước: [kích thước]
     - Ưu điểm: [ưu điểm]
- Kết thúc bằng:
  "Bạn quan tâm sản phẩm nào, mình tư vấn thêm nhé! 😊"

ĐỊNH DẠNG TRẢ LỜI CHÍNH SÁCH/TƯ VẤN:
- Không tự thêm danh sách sản phẩm nếu câu hỏi là tư vấn/chính sách.
- Trình bày bằng đoạn ngắn hoặc gạch đầu dòng.
- Không bịa thông tin ngoài ngữ cảnh.

NHẮC LẠI:
- Retrieval đã được thực hiện bằng câu hỏi hiện tại.
- Bạn chỉ nhận thêm 2 câu trả lời gần nhất để hiểu ngữ cảnh giao diện.
- Không được kéo nội dung cũ nếu câu hỏi hiện tại đã rõ ràng và không cần tham chiếu.
"""


def build_system_prompt(context: str, last_assistant_answers: str) -> str:
    ctx = context.strip() if context.strip() else "Không có dữ liệu liên quan."
    last = last_assistant_answers.strip() if last_assistant_answers.strip() else "Không có."

    return f"""
{SYSTEM_RULES}

[NGỮ CẢNH]
{ctx}

[2 CÂU TRẢ LỜI GẦN NHẤT TRÊN GIAO DIỆN]
{last}
""".strip()


# =========================================================
# LLM CALL
# =========================================================

def call_llm(
    question: str,
    context: str,
    last_assistant_answers: str,
) -> str:
    """
    Gọi Groq để sinh câu trả lời.

    Messages chỉ gồm:
    1. system: SYSTEM_RULES + context + last assistant answer
    2. user: câu hỏi hiện tại

    Không truyền toàn bộ history vào messages.
    """
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(context, last_assistant_answers)
        },
        {
            "role": "user",
            "content": question
        }
    ]

    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.3,
            max_completion_tokens=1024,
        )

        return resp.choices[0].message.content.strip()

    except Exception as e:
        print(f"[ERROR][LLM] Groq lỗi: {e}")

        if "429" in str(e):
            return "Xin lỗi, hệ thống đang bận. Bạn vui lòng thử lại sau vài giây nhé!"

        raise


# =========================================================
# ROUTES
# =========================================================
@app.get("/")
def root():
    return {
        "service": "Furniture RAG API",
        "status": "running",
        "version": "2.3.1",
        "llm": GROQ_MODEL,
        "retrieval": "question_only",
        "llm_history": "last_2_assistant_answers_only",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "groq_model": GROQ_MODEL,
        "embed": EMBED_MODEL,
        "milvus": MILVUS_URI,
        "collection": COLLECTION_NAME,
    }


@app.post("/chat", response_model=ChatResponse)
def chat_api(payload: ChatRequest):
    t0 = time.time()
    # Bước 0: nhận input
    # API lấy câu hỏi hiện tại, làm sạch history, rồi lấy 2 câu trả lời gần nhất của assistant.
    question = payload.question.strip()
    history = normalize_history(payload.history)
    last_assistant_answers = get_last_assistant_answers(history)

    if not question: # Nếu câu hỏi rỗng:
        return ChatResponse(
            answer="Bạn chưa nhập câu hỏi.",
            elapsed=0.0
        )

    request_time = now_str()
    # log request
    log_section("REQUEST")
    log_key_value("Time", request_time)
    log_key_value("Endpoint", "POST /chat")
    log_key_value("RAG mode", "retrieval = question_only, llm_context = last_2_assistant_answers_only")

    log_section("INPUT")
    log_key_value("Question", question)
    log_key_value("History messages received", len(history))

    log_section("LAST 2 ASSISTANT ANSWERS FROM UI")
    log_key_value("Used for LLM context", "yes" if last_assistant_answers else "no")
    log_key_value("Preview", preview_text(last_assistant_answers))

    # =====================================================
    # BƯỚC 1: CLASSIFY
    # =====================================================
    t1 = time.time()
    intent = classify_intent(question)
    classify_time = round(time.time() - t1, 2)

    log_section("CLASSIFY")
    log_key_value("Input used", "current user question only")
    log_key_value("Intent", intent)
    log_key_value("Time", f"{classify_time}s")

    context = ""
    product_docs = []
    policy_docs = []
    retrieval_time = 0.0

    # =====================================================
    # BƯỚC 2: RETRIEVAL
    # =====================================================
    t2 = time.time()

    log_section("RETRIEVAL")
    log_key_value("Query used", question)

    if intent == "search_product":
        log_key_value("Target collection filter", 'content_type == "product"')

        product_docs = search_product(question)
        retrieval_time = round(time.time() - t2, 2)
        context = build_product_context(product_docs)

        log_key_value("Result count", len(product_docs))
        log_key_value("Time", f"{retrieval_time}s")

        if product_docs:
            print("- Product results:")
            for i, d in enumerate(product_docs, 1):
                m = d.get("metadata", {})
                print(
                    f"  {i}. score={d['score']} | "
                    f"id={m.get('product_id', '')} | "
                    f"name={m.get('name', '')} | "
                    f"price={m.get('price_sale', '')}"
                )
        else:
            print("- Product results: Không có kết quả qua ngưỡng score.")

    elif intent == "search_policy":
        log_key_value("Target collection filter", 'content_type == "policy"')

        policy_docs = search_policy(question)
        retrieval_time = round(time.time() - t2, 2)
        context = build_policy_context(policy_docs)

        log_key_value("Result count", len(policy_docs))
        log_key_value("Time", f"{retrieval_time}s")

        if policy_docs:
            print("- Policy results:")
            for i, d in enumerate(policy_docs, 1):
                print(
                    f"  {i}. score={d['score']} | "
                    f"source={d.get('source', '')} | "
                    f"section={d.get('section', '')}"
                )
        else:
            print("- Policy results: Không có kết quả qua ngưỡng score.")

    else:
        retrieval_time = round(time.time() - t2, 2)
        log_key_value("Action", "answer_direct -> skip retrieval")
        log_key_value("Time", f"{retrieval_time}s")

    log_key_value("Context chars", len(context))

    # =====================================================
    # BƯỚC 3: LLM
    # =====================================================
    log_section("LLM")
    log_key_value("Model", GROQ_MODEL)
    log_key_value("Temperature", 0.3)
    log_key_value("System includes", "SYSTEM_RULES + retrieval context + last 2 assistant answers")
    log_key_value("User message", question)

    t3 = time.time()

    answer = call_llm( # LLM nhận
        question=question, # câu hỏi hiện tại
        context=context, # ngữ cảnh từ retrieval (có thể là sản phẩm hoặc chính sách)
        last_assistant_answers=last_assistant_answers # 2 câu trả lời gần nhất của assistant trên giao diện (dùng để hiểu câu hỏi tham chiếu, không dùng cho retrieval/search
    )

    llm_time = round(time.time() - t3, 2) # Tính thời gian LLM trả lời

    if not answer:
        answer = "Xin lỗi, tôi chưa có thông tin về vấn đề này."

    log_key_value("Time", f"{llm_time}s")
    log_key_value("Answer preview", preview_text(answer))

    # =====================================================
    # RESULT
    # =====================================================
    elapsed = round(time.time() - t0, 2)

    log_section("RESULT")
    log_key_value("Intent", intent)
    log_key_value("Product count", len(product_docs))
    log_key_value("Policy count", len(policy_docs))
    log_key_value("Classify time", f"{classify_time}s")
    log_key_value("Retrieval time", f"{retrieval_time}s")
    log_key_value("LLM time", f"{llm_time}s")
    log_key_value("Total elapsed", f"{elapsed}s")
    log_key_value("Answer chars", len(answer))

    log_chat_end()

    return ChatResponse( # trả về câu trả lời, intent, số sản phẩm và chính sách tìm được, thời gian xử lý
        answer=answer,
        intent=intent,
        product_count=len(product_docs),
        policy_count=len(policy_docs),
        elapsed=elapsed,
    )