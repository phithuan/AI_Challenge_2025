"""
task2_embed_and_insert.py
=========================
Embed full_description bằng BGE-M3 (Ollama) → insert vào Milvus.

Schema Milvus:
  raw_text      = full_description (văn bản embed, LLM đọc để trả lời)
  metadata_json = {name, category, price_sale, price_original, material, size, summary}
                  (structured data để build context nhanh, không cần parse raw_text)
  vector        = 1024 chiều BGE-M3

Yêu cầu:
  pip install pymilvus requests langchain langchain-text-splitters
  ollama serve + ollama pull bge-m3
  Milvus đang chạy port 19530
"""

import os, json, time, re, glob, requests
from pymilvus import MilvusClient, DataType
from langchain_text_splitters import RecursiveCharacterTextSplitter
from task1_prepare_data import prepare_all_chunks

# ─────────────────────────────────────────────────────────────
OLLAMA_URL      = "http://127.0.0.1:11434"
EMBED_MODEL     = "bge-m3"
VECTOR_DIM      = 1024
MILVUS_URI      = "http://localhost:19530"
COLLECTION_NAME = "furniture_rag"
BATCH_SIZE      = 8   # nhỏ vì BGE-M3 nặng trên CPU
# ─────────────────────────────────────────────────────────────


def embed_texts(texts: list[str]) -> list[list[float]]: # để đảm bảo trả về list vector, ngay cả khi chỉ gửi 1 text (Ollama có thể trả về dict thay vì list nếu input là 1 string duy nhất)
    """Gửi batch text tới Ollama /api/embed, trả về list vector 1024 chiều."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120 # tăng timeout vì BGE-M3 có thể chậm khi chạy trên CPU, đặc biệt với batch > 1
    )
    resp.raise_for_status() # nếu lỗi HTTP, sẽ ném exception để retry ở hàm gọi
    data = resp.json() # có thể trả về {"embedding": [...]} nếu input là 1 string, hoặc {"embeddings": [[...], [...], ...]} nếu input là list
    if "embeddings" in data: # trả về list vector nếu input là list
        return data["embeddings"] # Ollama version mới trả về "embeddings" khi input là list
    return [data["embedding"]]   # fallback Ollama version cũ


def recreate_collection(client: MilvusClient):
    """Xóa collection cũ + tạo lại. Phải xóa khi thay đổi schema hoặc dim."""
    if COLLECTION_NAME in client.list_collections():
        print(f"[Milvus] Xóa collection cũ '{COLLECTION_NAME}'...")
        client.drop_collection(COLLECTION_NAME)

    print(f"[Milvus] Tạo collection '{COLLECTION_NAME}' (dim={VECTOR_DIM})...")
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id",            DataType.INT64,        is_primary=True, auto_id=True)
    schema.add_field("content_type",  DataType.VARCHAR,      max_length=20)   # "product" | "policy"
    schema.add_field("chunk_type",    DataType.VARCHAR,      max_length=30)   # "full_description" | "heading_section" ...
    schema.add_field("raw_text",      DataType.VARCHAR,      max_length=2000) # văn bản embed + LLM đọc
    schema.add_field("metadata_json", DataType.VARCHAR,      max_length=2000) # structured data để build context
    schema.add_field("vector",        DataType.FLOAT_VECTOR, dim=VECTOR_DIM)

    idx = client.prepare_index_params()
    idx.add_index(
        field_name="vector",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200}
    )
    client.create_collection(collection_name=COLLECTION_NAME, schema=schema, index_params=idx)
    print("[Milvus] Tạo xong!\n")


def embed_and_insert(client: MilvusClient, chunks: list[dict]):
    """Embed từng batch → insert vào Milvus với retry khi timeout."""
    total = len(chunks)
    done  = 0
    t0    = time.time()
    print(f"[Embed] {total} chunk, batch={BATCH_SIZE}...")

    for start in range(0, total, BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        texts = [c["raw_text"] for c in batch]

        # Retry tối đa 3 lần
        for attempt in range(3):
            try:
                vectors = embed_texts(texts)
                break
            except requests.exceptions.Timeout:
                if attempt < 2:
                    print(f"  [Timeout] Thử lại lần {attempt+2}...")
                    time.sleep(2)
                else:
                    raise

        rows = []
        for i, chunk in enumerate(batch):
            # Lọc metadata: chỉ lưu kiểu primitive (str/int/float/bool)
            meta = {k: v for k, v in chunk["metadata"].items()
                    if isinstance(v, (str, int, float, bool))}
            rows.append({
                "content_type":  chunk["content_type"],
                "chunk_type":    chunk.get("chunk_type", "unknown"),
                "raw_text":      chunk["raw_text"][:1990],  # giới hạn VARCHAR(2000)
                "metadata_json": json.dumps(meta, ensure_ascii=False),
                "vector":        vectors[i]
            })

        client.insert(collection_name=COLLECTION_NAME, data=rows)
        done += len(batch)
        elapsed = time.time() - t0
        eta     = (total - done) / (done / elapsed) if done > 0 else 0
        print(f"  → {done}/{total} | {elapsed:.1f}s | ~{eta:.0f}s còn lại")

    client.flush(collection_name=COLLECTION_NAME)
    print(f"\n[Embed] Hoàn tất! {done} chunk trong {time.time()-t0:.1f}s.")


def verify(client: MilvusClient): # để kiểm tra nhanh sau khi insert, không phải kiểm tra chi tiết từng vector vì có thể quá nặng, chỉ cần confirm số lượng và mẫu dữ liệu đã đúng.
    """In thống kê nhanh để xác nhận data đúng."""
    client.load_collection(COLLECTION_NAME)
    stats    = client.get_collection_stats(COLLECTION_NAME)
    products = client.query(COLLECTION_NAME, filter='content_type == "product"',
                            output_fields=["id"], limit=1000)
    policies = client.query(COLLECTION_NAME, filter='content_type == "policy"',
                            output_fields=["id", "metadata_json"], limit=500)

    print("\n" + "="*55)
    print(f"  Model  : {EMBED_MODEL} (dim={VECTOR_DIM})")
    print(f"  Tổng   : {stats.get('row_count','?')} vector")
    print(f"  Product: {len(products)} chunk")
    print(f"  Policy : {len(policies)} chunk")

    # Thống kê policy theo file nguồn
    by_src: dict[str, int] = {}
    for p in policies:
        src = json.loads(p["metadata_json"]).get("source", "?")
        by_src[src] = by_src.get(src, 0) + 1
    for src, n in sorted(by_src.items()):
        print(f"    {src}: {n} chunk")

    # In mẫu product
    s = client.query(COLLECTION_NAME, filter='content_type == "product"',
                     output_fields=["raw_text", "metadata_json"], limit=1)
    if s:
        print(f"\n  Mẫu product raw_text:\n  {s[0]['raw_text'][:150]}...")
        print(f"  Mẫu metadata_json   :\n  {s[0]['metadata_json'][:150]}...")
    print("="*55)


if __name__ == "__main__":
    print("="*55)
    print(f"  TASK 2: EMBED ({EMBED_MODEL}) → MILVUS")
    print("="*55 + "\n")

    # 1. Test kết nối Ollama
    print(f"[Test] Ollama embed ({EMBED_MODEL})...")
    vecs = embed_texts(["test"])
    assert len(vecs[0]) == VECTOR_DIM, f"Dim sai: {len(vecs[0])}"
    print(f"[Test] OK — dim={len(vecs[0])}\n")

    # 2. Kết nối Milvus
    print(f"[Milvus] Kết nối {MILVUS_URI}...")
    client = MilvusClient(uri=MILVUS_URI)

    # 3. Tạo lại collection
    recreate_collection(client)

    # 4. Chuẩn bị chunk từ task1
    chunks = prepare_all_chunks()

    # 5. Embed + Insert
    embed_and_insert(client, chunks)

    # 6. Kiểm tra
    verify(client)
    print("\n✅ Hoàn tất! Chạy chat_bot_rag.py để test.")





