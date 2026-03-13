# app/milvus_utils.py

from django.conf import settings

milvus_client = None
model = None
GoogleTranslator = None
clip = None

if getattr(settings, "USE_MILVUS", False):
    try:
        import clip
        from deep_translator import GoogleTranslator
        from pymilvus import MilvusClient

        milvus_client = MilvusClient(uri="http://localhost:19530")
        model, preprocess = clip.load("ViT-B/32")
        model.eval()

        print("Milvus + CLIP loaded successfully")

    except Exception as e:
        print("Milvus disabled:", e)
        milvus_client = None
        model = None


def search_milvus(query_vi: str, top_k=6):
    """
    Nếu USE_MILVUS = False → trả về rỗng.
    Nếu bật → chạy semantic search.
    """

    if not getattr(settings, "USE_MILVUS", False):
        return []

    if not milvus_client or not model:
        return []

    # Dịch tiếng Việt sang tiếng Anh
    query_en = GoogleTranslator(source="vi", target="en").translate(query_vi)

    tokens = clip.tokenize(query_en)
    text_features = model.encode_text(tokens)
    text_features /= text_features.norm(dim=-1, keepdim=True)
    query_vector = text_features.squeeze().tolist()

    search_results = milvus_client.search(
        collection_name="image_collection",
        data=[query_vector],
        limit=top_k,
        output_fields=["filepath"]
    )

    hits = []
    for result in search_results[0]:
        filepath = result["entity"]["filepath"]
        relative_path = filepath.replace(
            r"D:/Big_project_2025/WebShop/app/static", ""
        ).replace("\\", "/").lstrip("/")

        hits.append({"filepath": relative_path})

    return hits