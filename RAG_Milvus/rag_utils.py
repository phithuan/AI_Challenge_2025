from pymilvus import MilvusClient
import os
from sentence_transformers import SentenceTransformer

# chỉ định chỗ lưu cache
os.environ["HF_HOME"] = r"D:\Big_project_2025\huggingface_cache"

# tải model từ HuggingFace (sẽ tự lưu vào HF_HOME)
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
# hàm tiện ích để sinh embeddings cho text

def emb_text(text: str):
    return model.encode(text).tolist()

# Kết nối Milvus
milvus_client = MilvusClient(uri="http://localhost:19530")
collection_name = "my_rag_collection"

def search_text(question: str, top_k=1): # Tìm kiếm văn bản trong Milvus
    """Tìm kiếm câu trả lời tốt nhất từ Milvus"""
    search_res = milvus_client.search(
        collection_name=collection_name,
        data=[emb_text(question)],
        limit=top_k,
        search_params={"metric_type": "IP", "params": {}},
        output_fields=["text"],
    )
    if not search_res[0]:
        return "❌ Không tìm thấy dữ liệu phù hợp"
    return search_res[0][0]["entity"]["text"]
