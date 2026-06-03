"""
rag_api.py
==========
Microservice API cho Chatbot RAG nội thất.

Chạy bằng:
    uvicorn rag_api:app --host 127.0.0.1 --port 8010

Django WebShop sẽ gọi:
    http://127.0.0.1:8010/chat

Yêu cầu:
    pip install fastapi uvicorn pymilvus requests

Cần chạy trước:
    ollama serve
    ollama pull bge-m3
    ollama pull gemma2:2b

Milvus:
    http://localhost:19530

Attu UI:
    http://localhost:8000/#/connect
"""

import json
import time
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI
from pydantic import BaseModel
from pymilvus import MilvusClient


# =========================================================
# CẤU HÌNH
# =========================================================

OLLAMA_URL = "http://127.0.0.1:11434"

EMBED_MODEL = "bge-m3"
VECTOR_DIM = 1024

LLM_MODEL = "gemma2:2b"
MILVUS_URI = "http://localhost:19530"
COLLECTION_NAME = "furniture_rag"

TOP_K_PRODUCT = 5
TOP_K_POLICY = 8

EF_SEARCH = 150 # càng cao càng chậm nhưng có thể tìm được kết quả tốt hơn, thường để 100-200 với COSINE

MIN_SCORE_PRODUCT = 0.55
MIN_SCORE_POLICY = 0.50

TIMEOUT_EMBED = 60
TIMEOUT_CLASSIFY = 30
TIMEOUT_LLM = 300

# Số message lịch sử dùng để tạo search query
MAX_HISTORY_FOR_SEARCH = 4

# Số message lịch sử đưa vào LLM
MAX_HISTORY_FOR_LLM = 5


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="Furniture RAG Chatbot API",
    version="1.0.0",
)

milvus_client: Optional[MilvusClient] = None


# =========================================================
# REQUEST / RESPONSE
# =========================================================

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    answer: str
    intent: str = ""
    product_count: int = 0
    policy_count: int = 0
    elapsed: float = 0.0


# =========================================================
# HISTORY PROCESSING
# =========================================================

def normalize_history(history: List[ChatMessage]) -> List[Dict[str, str]]:
    """
    Chuẩn hóa history frontend gửi lên.

    Chỉ giữ:
    - role: user hoặc assistant
    - content: không rỗng

    Mục tiêu:
    - Tránh đưa dữ liệu lỗi vào LLM.
    - Tránh role lạ làm Ollama lỗi.
    """
    clean_history = []

    for item in history:
        role = item.role.strip().lower()
        content = item.content.strip()

        if role not in ["user", "assistant"]:
            continue

        if not content:
            continue

        clean_history.append({
            "role": role,
            "content": content,
        })

    return clean_history


def build_search_query(question: str, history: List[Dict[str, str]]) -> str:
    """
    Tạo search_query rõ nghĩa hơn để search Milvus.

    Ví dụ:
    Lịch sử:
        User: Tôi cần bàn ăn 4 ghế
        Bot : Dạ, cửa hàng có ...

    Câu mới:
        Cái nào rẻ nhất?

    Search query:
        Ngữ cảnh hội thoại trước đó:
        Khách đã hỏi: Tôi cần bàn ăn 4 ghế
        Chatbot đã trả lời: Dạ, cửa hàng có ...

        Câu hỏi hiện tại:
        Cái nào rẻ nhất?

    Nhờ vậy Milvus không chỉ search câu "Cái nào rẻ nhất?"
    mà hiểu nó đang liên quan đến bàn ăn 4 ghế.
    """
    question = question.strip()

    if not history:
        return question

    recent_history = history[-MAX_HISTORY_FOR_SEARCH:]
    history_lines = []

    for msg in recent_history:
        role = msg["role"]
        content = msg["content"].strip()

        if not content:
            continue

        if role == "user":
            history_lines.append(f"Khách đã hỏi: {content}")

        elif role == "assistant":
            # Cắt ngắn câu trả lời bot để tránh search query quá dài
            short_answer = content[:300]
            history_lines.append(f"Chatbot đã trả lời: {short_answer}")

    history_text = "\n".join(history_lines).strip()

    if not history_text:
        return question

    search_query = f"""Ngữ cảnh hội thoại trước đó:
{history_text}

Câu hỏi hiện tại:
{question}

Hãy hiểu câu hỏi hiện tại dựa trên ngữ cảnh trên."""
    
    return search_query.strip()


# =========================================================
# EMBEDDING
# =========================================================

def embed(text: str) -> List[float]:
    """
    Dùng BGE-M3 qua Ollama để chuyển text thành vector 1024 chiều.
    """
    resp = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json={
            "model": EMBED_MODEL,
            "input": [text],
        },
        timeout=TIMEOUT_EMBED,
    )
    resp.raise_for_status()

    data = resp.json()

    if "embeddings" in data:
        vector = data["embeddings"][0]
    else:
        vector = data["embedding"]

    if len(vector) != VECTOR_DIM:
        raise ValueError(f"Embedding dimension sai: {len(vector)} != {VECTOR_DIM}")

    return vector


# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
def startup_event():
    """
    Khởi tạo Milvus một lần khi API start.
    Không tạo client lại mỗi request để tránh chậm.
    """
    global milvus_client

    print("=" * 60)
    print("[RAG API] Khởi động service...")

    print(f"[RAG API] Kiểm tra Ollama embedding model: {EMBED_MODEL}")
    test_vec = embed("test")
    print(f"[RAG API] Embed OK, dim={len(test_vec)}")

    print(f"[RAG API] Kết nối Milvus: {MILVUS_URI}")
    milvus_client = MilvusClient(uri=MILVUS_URI)

    print(f"[RAG API] Load collection: {COLLECTION_NAME}")
    milvus_client.load_collection(COLLECTION_NAME)

    print("[RAG API] Sẵn sàng nhận câu hỏi.")
    print("=" * 60)


# =========================================================
# INTENT CLASSIFICATION
# =========================================================

CLASSIFY_PROMPT = """Tôi có một câu hỏi, bạn phân tích câu hỏi và phân loại nó vào một trong ba loại:
- search_product : tư vấn, tìm kiếm sản phẩm, hỏi về giá, chất liệu, kích thước
- search_policy  : hỏi về bảo hành, đổi trả, vận chuyển, chính sách, quy định, thông tin liên hệ, thời gian hoạt động mở cửa hoặc đóng cửa
- answer_direct  : chào hỏi thông thường, cảm ơn, tạm biệt, phép tính đơn giản, ngoài các ý search_product và search_policy

Chỉ trả về đúng tên loại, không thêm giải thích.

Câu hỏi: {query}
Loại:"""


def classify_intent(query: str) -> str:
    """
    Phân loại intent.
    Dùng query đã được làm rõ bằng history.
    Nếu lỗi thì fallback về search_product.
    """
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": CLASSIFY_PROMPT.format(query=query),
                "stream": False,
                "options": {
                    "num_predict": 10,
                    "temperature": 0,
                },
            },
            timeout=TIMEOUT_CLASSIFY,
        )
        resp.raise_for_status()

        result = resp.json().get("response", "").strip().lower()

        if "policy" in result or "chính sách" in result or "bảo hành" in result:
            return "search_policy"

        if "direct" in result or "answer_direct" in result or "chào" in result:
            return "answer_direct"

        return "search_product"

    except Exception as e:
        print(f"[Classify] Lỗi: {e} -> fallback search_product")
        return "search_product"


# =========================================================
# SEARCH PRODUCT
# =========================================================

def search_product(query: str) -> List[Dict[str, Any]]:
    """
    Search sản phẩm trong Milvus.
    Product chỉ cần metadata_json vì dữ liệu sản phẩm đã có cấu trúc.
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
            "params": {
                "ef": EF_SEARCH,
            },
        },
    )

    results = []

    for hit in hits[0]:
        score = hit["distance"]

        if score < MIN_SCORE_PRODUCT:
            continue

        meta = json.loads(hit["entity"]["metadata_json"])

        results.append({
            "score": round(score, 3),
            "metadata": meta,
        })

    return results


# =========================================================
# SEARCH POLICY
# =========================================================

def search_policy(query: str) -> List[Dict[str, Any]]:
    """
    Search chính sách trong Milvus.
    Policy cần raw_text vì nội dung trả lời nằm trong văn bản chính sách.
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
            "params": {
                "ef": EF_SEARCH,
            },
        },
    )

    results = []

    for hit in hits[0]:
        score = hit["distance"]

        if score < MIN_SCORE_POLICY:
            continue

        meta = json.loads(hit["entity"]["metadata_json"])

        results.append({
            "score": round(score, 3),
            "text": hit["entity"]["raw_text"],
            "source": meta.get("source", ""),
            "section": meta.get("section", ""),
        })

    return results


# =========================================================
# BUILD CONTEXT
# =========================================================

def format_price(value: Any) -> str:
    """
    Format tiền Việt Nam: 3990000 -> 3.990.000đ
    """
    try:
        return f"{int(float(value)):,}đ".replace(",", ".")
    except Exception:
        return ""


def build_product_context(docs: List[Dict[str, Any]]) -> str:
    """
    Format dữ liệu sản phẩm thành context rõ ràng cho LLM.
    """
    if not docs:
        return ""

    lines = [f"=== CÓ {len(docs)} SẢN PHẨM LIÊN QUAN ==="]

    for i, doc in enumerate(docs, 1):
        meta = doc["metadata"]

        name = meta.get("name", "")
        category = meta.get("category", "")
        price_sale = meta.get("price_sale", 0)
        price_original = meta.get("price_original", 0)
        material = meta.get("material", "")
        size = meta.get("size", "")
        summary = meta.get("summary", "")

        lines.append(f"\n[SP{i}] {name}")

        if category:
            lines.append(f"  Danh mục  : {category}")

        if price_sale:
            price_text = format_price(price_sale)

            try:
                if price_original and float(price_original) > float(price_sale):
                    discount = round(
                        (float(price_original) - float(price_sale))
                        / float(price_original)
                        * 100
                    )
                    price_text += f" (giảm {discount}% từ {format_price(price_original)})"
            except Exception:
                pass

            lines.append(f"  Giá bán   : {price_text}")

        if material:
            lines.append(f"  Chất liệu : {material}")

        if size:
            lines.append(f"  Kích thước: {size}")

        if summary:
            lines.append(f"  Ưu điểm   : {summary}")

    return "\n".join(lines)


def build_policy_context(docs: List[Dict[str, Any]]) -> str:
    """
    Format dữ liệu chính sách thành context cho LLM.
    """
    if not docs:
        return ""

    lines = ["=== THÔNG TIN CHÍNH SÁCH ==="]

    for i, item in enumerate(docs, 1):
        source = item.get("source", "")
        section = item.get("section", "")
        text = item.get("text", "")

        src = ""

        if source:
            src = f"(nguồn: {source}"
            if section:
                src += f" | mục: {section}"
            src += ")"

        lines.append(f"\n[CS{i}] {src}")
        lines.append(text)

    return "\n".join(lines)


# =========================================================
# LLM
# =========================================================

SYSTEM_RULES = """Bạn là nhân viên tư vấn bán hàng nội thất. Trả lời bằng tiếng Việt, thân thiện, rõ ràng.

LUẬT BẮT BUỘC:
1. CHỈ dùng thông tin trong [NGỮ CẢNH]. KHÔNG tự thêm số liệu - thông số - ngày giờ bên ngoài.
2. Nếu có thông tin → trả lời đầy đủ, cụ thể ngay.
3. Nếu không có dữ liệu phù hợp, hãy nói: "Xin lỗi, tôi chưa có thông tin về vấn đề này."
4. Khi giới thiệu sản phẩm, cần có: tên, giá, chất liệu, kích thước, ưu điểm.
    liệt kê nhiều sản phẩm:
    Dạ, cửa hàng có [N] sản phẩm phù hợp:
    1. [Tên SP1]
    - Giá: [giá]
    - Chất liệu: [chất liệu]
    - Kích thước: [kích thước]
    - Ưu điểm: [Ưu điểm nổi bật của sản phẩm này]

    2. [Tên SP2]
    ...
5. Nếu khách chào hỏi, hãy chào lại tự nhiên và hỏi khách cần tìm sản phẩm hay chính sách gì.
6. Nếu câu hỏi hiện tại là câu nối tiếp như 'cái nào rẻ nhất', 'cái đó', 'so sánh 2 cái', hãy hiểu dựa trên lịch sử hội thoại gần nhất."""


def build_system_prompt(context: str) -> str:
    if context:
        ctx = f"[NGỮ CẢNH]\n{context}"
    else:
        ctx = "[NGỮ CẢNH]\nKhông có dữ liệu liên quan."

    return f"{SYSTEM_RULES}\n\n{ctx}"


def call_llm(
    question: str,
    context: str,
    history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Gọi Ollama /api/chat.
    Có truyền history để LLM hiểu câu hỏi nối tiếp.
    """
    if history is None:
        history = []

    llm_history = history[-MAX_HISTORY_FOR_LLM:]

    messages = [
        {
            "role": "system",
            "content": build_system_prompt(context),
        },
        *llm_history,
        {
            "role": "user",
            "content": question,
        },
    ]

    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": 4096,
                "temperature": 0.3,
            },
        },
        timeout=TIMEOUT_LLM,
    )
    resp.raise_for_status()

    data = resp.json()
    return data.get("message", {}).get("content", "").strip()


# =========================================================
# ROUTES
# =========================================================

@app.get("/")
def root():
    return {
        "service": "Furniture RAG API",
        "status": "running",
        "chat_endpoint": "/chat",
        "health_endpoint": "/health",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "rag_api",
        "collection": COLLECTION_NAME,
        "embed_model": EMBED_MODEL,
        "llm_model": LLM_MODEL,
        "milvus_uri": MILVUS_URI,
        "ollama_url": OLLAMA_URL,
    }


@app.post("/chat", response_model=ChatResponse)
def chat_api(payload: ChatRequest):
    t0 = time.time()

    question = payload.question.strip()
    history = normalize_history(payload.history)
    search_query = build_search_query(question, history)

    print("\n" + "=" * 80)
    print("[CHAT REQUEST]")
    print(f"Câu hỏi gốc: {question}")
    print(f"Số message history nhận được: {len(history)}")
    print("[SEARCH QUERY]")
    print(search_query[:1000])
    if len(search_query) > 1000:
        print("... [search_query bị cắt ngắn khi log]")

    if not question:
        print("[KẾT QUẢ] Câu hỏi rỗng")
        print("=" * 80)

        return ChatResponse(
            answer="Bạn chưa nhập câu hỏi.",
            intent="",
            product_count=0,
            policy_count=0,
            elapsed=0.0,
        )

    # Bước 1: phân loại intent bằng search_query để hiểu câu nối tiếp
    t_intent = time.time()
    intent = classify_intent(search_query)
    intent_time = round(time.time() - t_intent, 2)

    print(f"[BƯỚC 1] Intent: {intent} | time={intent_time}s")

    context = ""
    product_docs = []
    policy_docs = []

    # Bước 2: search dữ liệu bằng search_query
    t_search = time.time()

    if intent == "search_product":
        product_docs = search_product(search_query)
        context = build_product_context(product_docs)

        print(f"[BƯỚC 2] Search product: {len(product_docs)} kết quả")

        for i, doc in enumerate(product_docs, 1):
            meta = doc.get("metadata", {})
            print(
                f"  SP{i} | score={doc.get('score')} | "
                f"name={meta.get('name', '')} | "
                f"price={meta.get('price_sale', '')} | "
                f"material={meta.get('material', '')}"
            )

    elif intent == "search_policy":
        policy_docs = search_policy(search_query)
        context = build_policy_context(policy_docs)

        print(f"[BƯỚC 2] Search policy: {len(policy_docs)} kết quả")

        for i, doc in enumerate(policy_docs, 1):
            print(
                f"  CS{i} | score={doc.get('score')} | "
                f"source={doc.get('source', '')} | "
                f"section={doc.get('section', '')}"
            )

    else:
        print("[BƯỚC 2] answer_direct: không search Milvus")

    search_time = round(time.time() - t_search, 2)
    print(f"[BƯỚC 2] Search time={search_time}s")

    # In context ngắn để debug, không in quá dài
    if context:
        print("[CONTEXT PREVIEW]")
        print(context[:1000])
        if len(context) > 1000:
            print("... [context bị cắt ngắn khi log]")
    else:
        print("[CONTEXT PREVIEW] Không có context")

    # Bước 3: gọi LLM với history
    t_llm = time.time()
    answer = call_llm(question, context, history)
    llm_time = round(time.time() - t_llm, 2)

    if not answer:
        answer = "Xin lỗi, tôi chưa có thông tin về vấn đề này."

    elapsed = round(time.time() - t0, 2)

    print(f"[BƯỚC 3] LLM time={llm_time}s")
    print("[ANSWER PREVIEW]")
    print(answer[:1000])
    if len(answer) > 1000:
        print("... [answer bị cắt ngắn khi log]")

    print("[TỔNG KẾT]")
    print(f"intent={intent}")
    print(f"product_count={len(product_docs)}")
    print(f"policy_count={len(policy_docs)}")
    print(f"elapsed={elapsed}s")
    print("=" * 80)

    return ChatResponse(
        answer=answer,
        intent=intent,
        product_count=len(product_docs),
        policy_count=len(policy_docs),
        elapsed=elapsed,
    )