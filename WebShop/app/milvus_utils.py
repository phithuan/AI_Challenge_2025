# app/milvus_utils.py
import clip
from PIL import Image
from deep_translator import GoogleTranslator
from pymilvus import MilvusClient

# =========================
# 1. Init Milvus + CLIP
# =========================
milvus_client = MilvusClient(uri="http://localhost:19530")

model, preprocess = clip.load("ViT-B/32")
model.eval()

# =========================
# 2. Encode hàm
# =========================
def encode_text(text: str):
    tokens = clip.tokenize(text)
    text_features = model.encode_text(tokens)
    text_features /= text_features.norm(dim=-1, keepdim=True)
    return text_features.squeeze().tolist()

# =========================
# 3. Search Milvus
# =========================
def search_milvus(query_vi: str, top_k=6):
    # Dịch tiếng Việt sang tiếng Anh
    query_en = GoogleTranslator(source="vi", target="en").translate(query_vi)

    # Encode thành vector
    query_vector = encode_text(query_en)

    # Gọi Milvus search
    search_results = milvus_client.search(
        collection_name="image_collection",
        data=[query_vector],
        limit=top_k,
        output_fields=["filepath"]
    )

    # Parse kết quả
    hits = [] # danh sách kết quả
    for result in search_results[0]:
        # Chuyển đường dẫn tuyệt đối thành tương đối
        filepath = result["entity"]["filepath"]
        relative_path = filepath.replace(r"D:/Big_project_2025/WebShop/app/static", "").replace("\\", "/").lstrip("/") # Windows path fix + remove leading slash
        hits.append({"filepath": relative_path})
    return hits 
