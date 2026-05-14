"""
task2_embed_and_insert.py  —  BGE-M3 qua Ollama
=================================================
Thay đổi so với phiên bản SentenceTransformer cũ:

  [1] EMBEDDING MODEL
      Cũ : SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2") — 384 dim
      Mới: BGE-M3 qua Ollama REST API /api/embed — 1024 dim

      Lý do dùng REST API thay vì thư viện Python:
        - BGE-M3 cài qua "ollama pull bge-m3" chỉ expose qua HTTP
        - Không có Python package trực tiếp cho Ollama embedding
        - REST API đơn giản, không cần cài thêm gì

  [2] VECTOR_DIM: 384 → 1024
      Collection Milvus phải xóa và tạo lại (schema thay đổi)

  [3] BATCH SIZE: giảm từ 32 → 8
      BGE-M3 (566M params, F16) nặng hơn nhiều so với MiniLM (22M params)
      Gọi API từng batch nhỏ để tránh timeout và OOM

  [4] NORMALIZE: BGE-M3 qua Ollama đã normalize sẵn
      Không cần normalize thêm phía client

Yêu cầu:
  - Ollama đang chạy: ollama serve
  - BGE-M3 đã pull:  ollama pull bge-m3
  - Milvus đang chạy: port 19530
  - pip install pymilvus requests
"""

import os
import json
import time
import requests
from pymilvus import MilvusClient, DataType

from task1_prepare_data import prepare_all_chunks

# ─────────────────────────────────────────────────────────────
# CẤU HÌNH
# ─────────────────────────────────────────────────────────────
OLLAMA_URL      = "http://127.0.0.1:11434"
EMBED_MODEL     = "bge-m3"           # model đã pull qua ollama
VECTOR_DIM      = 1024               # BGE-M3 embedding length
BATCH_SIZE      = 8                  # nhỏ hơn vì model nặng hơn

MILVUS_URI      = "http://localhost:19530"
COLLECTION_NAME = "furniture_rag"


# ═════════════════════════════════════════════════════════════
# EMBEDDING QUA OLLAMA REST API
# ═════════════════════════════════════════════════════════════

def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Gửi batch text tới Ollama /api/embed, trả về list vector.

    Ollama /api/embed nhận:
      {
        "model": "bge-m3",
        "input": ["text1", "text2", ...]   ← list string
      }

    Ollama trả về:
      {
        "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]]
      }

    BGE-M3 qua Ollama đã normalize vector sẵn (unit norm),
    nên dùng trực tiếp với COSINE similarity trong Milvus.
    """
    payload  = {"model": EMBED_MODEL, "input": texts} # <--- ĐÂY LÀ NƠI GỬI TEXTS ĐẾN OLLAMA ĐỂ NHẬN VECTOR EMBEDDING ---  <--- "input" chứa nội dung raw_text
    response = requests.post( # GỬI YÊU CẦU EMBEDDING QUA REST API
        f"{OLLAMA_URL}/api/embed", # <--- ĐƯỜNG DẪN API EMBEDDING CỦA OLLAMA
        json=payload, # GỬI DỮ LIỆU DƯỚI DẠNG JSON
        timeout=120   # BGE-M3 nặng hơn, timeout dài hơn
    )
    response.raise_for_status()
    data = response.json()

    # Ollama trả về {"embeddings": [[...]]} hoặc {"embedding": [...]}
    # (tùy version Ollama) — xử lý cả hai trường hợp
    if "embeddings" in data:
        return data["embeddings"]
    elif "embedding" in data:
        # Version cũ: chỉ 1 vector
        return [data["embedding"]]
    else:
        raise ValueError(f"Ollama response không có 'embeddings': {list(data.keys())}")


def test_embedding_connection() -> int:
    """
    Kiểm tra kết nối Ollama và BGE-M3 trước khi chạy pipeline.
    Trả về số chiều vector để xác nhận đúng model.
    """
    print(f"[Kiểm tra] Test kết nối Ollama embed ({EMBED_MODEL})...")
    try:
        vecs = embed_texts(["test kết nối"])
        dim  = len(vecs[0])
        print(f"[Kiểm tra] OK — vector dim = {dim}")
        if dim != VECTOR_DIM:
            raise ValueError(
                f"Vector dim thực tế ({dim}) khác VECTOR_DIM cấu hình ({VECTOR_DIM})!\n"
                f"Hãy cập nhật VECTOR_DIM = {dim} trong file này."
            )
        return dim
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Không kết nối được Ollama!\n"
            "Hãy chạy: ollama serve\n"
            "Và đảm bảo: ollama pull bge-m3"
        )


# ═════════════════════════════════════════════════════════════
# MILVUS — TẠO COLLECTION
# ═════════════════════════════════════════════════════════════

def recreate_collection(client: MilvusClient):
    """
    Xóa collection cũ (dim 384) và tạo lại với dim 1024.
    Phải xóa vì Milvus không cho phép thay đổi dim của collection đã tạo.
    """
    existing = client.list_collections()
    if COLLECTION_NAME in existing:
        print(f"[Milvus] Xóa collection cũ '{COLLECTION_NAME}' (dim cũ != 1024)...")
        client.drop_collection(COLLECTION_NAME)
        print(f"[Milvus] Đã xóa.")

    print(f"[Milvus] Tạo collection '{COLLECTION_NAME}' (dim={VECTOR_DIM})...")

    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)

    # Các trường dữ liệu
    schema.add_field("id",            DataType.INT64,        is_primary=True, auto_id=True)
    schema.add_field("content_type",  DataType.VARCHAR,      max_length=20)
    schema.add_field("chunk_type",    DataType.VARCHAR,      max_length=30)
    schema.add_field("raw_text",      DataType.VARCHAR,      max_length=2000)
    schema.add_field("metadata_json", DataType.VARCHAR,      max_length=1000)
    schema.add_field("vector",        DataType.FLOAT_VECTOR, dim=VECTOR_DIM)

    # Index HNSW + COSINE — tốt nhất cho semantic search văn bản
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="HNSW",
        metric_type="COSINE",
        params={
            "M":              16,    # số neighbor mỗi node (16-64, cao hơn = chính xác hơn, chậm hơn)
            "efConstruction": 200    # độ sâu tìm kiếm lúc build index (cao hơn = index tốt hơn)
        }
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
        index_params=index_params
    )
    print(f"[Milvus] Tạo xong!\n")


# ═════════════════════════════════════════════════════════════
# EMBED + INSERT
# ═════════════════════════════════════════════════════════════

def embed_and_insert(client: MilvusClient, chunks: list[dict]):
    """
    Gọi Ollama embed từng batch → insert vào Milvus.

    Dùng BATCH_SIZE nhỏ (8) vì BGE-M3 (566M params F16) nặng hơn
    nhiều so với MiniLM (22M params) — tránh timeout Ollama.
    """
    total      = len(chunks)
    inserted   = 0
    start_time = time.time()

    print(f"[Embed] Bắt đầu embedding {total} chunk "
          f"(model={EMBED_MODEL}, batch={BATCH_SIZE})...")
    print(f"[Embed] Lưu ý: BGE-M3 chậm hơn MiniLM, vui lòng chờ...")

    for batch_start in range(0, total, BATCH_SIZE):
        batch = chunks[batch_start : batch_start + BATCH_SIZE]
        texts = [c["raw_text"] for c in batch]

        # Gọi Ollama embed — có retry khi timeout
        max_retry = 3
        vectors   = None
        for attempt in range(max_retry):
            try:
                vectors = embed_texts(texts) # <--- ĐÂY LÀ LỆNH THỰC THI BIẾN TEXT THÀNH VECTOR
                break
            except requests.exceptions.Timeout:
                if attempt < max_retry - 1:
                    print(f"  [Timeout] Thử lại lần {attempt + 2}...")
                    time.sleep(2)
                else:
                    raise

        if vectors is None:
            raise RuntimeError("Embed thất bại sau 3 lần thử")

        # Chuẩn bị data insert
        data_to_insert = []
        for i, chunk in enumerate(batch):
            # Chỉ lưu metadata có kiểu string/number (tránh lỗi JSON)
            meta_clean = {
                k: v for k, v in chunk["metadata"].items()
                if isinstance(v, (str, int, float, bool))
            }
            data_to_insert.append({
                "content_type":  chunk["content_type"],
                "chunk_type":    chunk.get("chunk_type", "unknown"),
                "raw_text":      chunk["raw_text"][:1990],   # giới hạn Milvus VARCHAR(2000)
                "metadata_json": json.dumps(meta_clean, ensure_ascii=False),
                "vector":        vectors[i]
            })

        client.insert(collection_name=COLLECTION_NAME, data=data_to_insert)
        inserted += len(batch)

        elapsed = time.time() - start_time
        speed   = inserted / elapsed if elapsed > 0 else 0
        eta     = (total - inserted) / speed if speed > 0 else 0
        print(f"  → {inserted}/{total} chunk | {elapsed:.1f}s | ~{eta:.0f}s còn lại")

    client.flush(collection_name=COLLECTION_NAME)
    elapsed_total = time.time() - start_time
    print(f"\n[Embed] Hoàn tất! {inserted} chunk trong {elapsed_total:.1f}s.")


# ═════════════════════════════════════════════════════════════
# KIỂM TRA
# ═════════════════════════════════════════════════════════════

def verify_data(client: MilvusClient):
    """In thống kê sau insert để xác nhận dữ liệu đúng."""
    client.load_collection(COLLECTION_NAME)
    stats = client.get_collection_stats(COLLECTION_NAME)

    products = client.query(COLLECTION_NAME, filter='content_type == "product"',
                            output_fields=["id"], limit=5000)
    policies = client.query(COLLECTION_NAME, filter='content_type == "policy"',
                            output_fields=["id", "metadata_json"], limit=500)

    print("\n" + "="*60)
    print(f"[Kiểm tra] Embedding model : {EMBED_MODEL} (dim={VECTOR_DIM})")
    print(f"[Kiểm tra] Tổng vector     : {stats.get('row_count', '?')}")
    print(f"[Kiểm tra] Product chunk   : {len(products)}")
    print(f"[Kiểm tra] Policy chunk    : {len(policies)}")

    # Thống kê policy theo source file
    by_source: dict[str, int] = {}
    for p in policies:
        meta = json.loads(p["metadata_json"])
        src  = meta.get("source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1
    for src, cnt in sorted(by_source.items()):
        print(f"               {src}: {cnt} chunk")

    # Mẫu kiểm tra
    s_prod = client.query(COLLECTION_NAME, filter='content_type == "product"',
                          output_fields=["chunk_type", "raw_text"], limit=1)
    s_pol  = client.query(COLLECTION_NAME, filter='content_type == "policy"',
                          output_fields=["chunk_type", "raw_text"], limit=1)

    print("\n--- Mẫu PRODUCT ---")
    if s_prod:
        print(f"  chunk_type: {s_prod[0]['chunk_type']}")
        print(f"  {s_prod[0]['raw_text'][:150]}")

    print("\n--- Mẫu POLICY ---")
    if s_pol:
        print(f"  chunk_type: {s_pol[0]['chunk_type']}")
        print(f"  {s_pol[0]['raw_text'][:200]}")
    print("="*60)


# ═════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print(f"  TASK 2: EMBED ({EMBED_MODEL}) & INSERT → MILVUS")
    print("=" * 60 + "\n")

    # 1. Kiểm tra Ollama + BGE-M3 trước khi làm gì
    test_embedding_connection()

    # 2. Kết nối Milvus
    print(f"\n[Milvus] Kết nối {MILVUS_URI}...")
    client = MilvusClient(uri=MILVUS_URI)
    print("[Milvus] OK!")

    # 3. Xóa collection cũ (dim 384) + tạo lại (dim 1024)
    recreate_collection(client)

    # 4. Chuẩn bị chunk từ task1
    all_chunks = prepare_all_chunks()

    # 5. Embed + Insert
    embed_and_insert(client, all_chunks)

    # 6. Xác nhận
    verify_data(client)

    print("\n✅ Hoàn tất! Chạy chat_bot_rag.py để test.")