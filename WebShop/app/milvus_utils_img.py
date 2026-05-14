# app/milvus_utils.py
import torch                                     # Thư viện tính toán tensor, hỗ trợ chạy mô hình trên GPU/CPU
import clip                                      # Thư viện CLIP của OpenAI để xử lý hình ảnh và văn bản
from sentence_transformers import SentenceTransformer # Thư viện hỗ trợ load mô hình Transformer (đa ngôn ngữ)
from pymilvus import MilvusClient               # Thư viện kết nối và thao tác với cơ sở dữ liệu Vector Milvus
from PIL import Image                            # Thư viện xử lý hình ảnh (mở file, chuyển đổi hệ màu)
import os                                        # Thư viện tương tác với hệ điều hành (đường dẫn file)

# Cấu hình thiết bị chạy AI
device = "cuda" if torch.cuda.is_available() else "cpu" # Ưu tiên chạy GPU (cuda) để tăng tốc, nếu không có thì chạy CPU

# ==============================
# 1. ĐƯỜNG DẪN MÔ HÌNH CỤC BỘ (Offline Models)
# ==============================
# Thư mục chứa mô hình trích xuất đặc trưng văn bản đa ngôn ngữ (Tiếng Việt)
TEXT_MODEL_PATH = r"D:\Big_project_2025\CODE_THTN\clip-ViT-B-32-multilingual-v1"
# Thư mục chứa mô hình trích xuất đặc trưng hình ảnh (CLIP ViT-B-32)
IMAGE_MODEL_PATH = r"D:\Big_project_2025\CODE_THTN\clip-ViT-B-32"

# ==============================
# 2. KHỞI TẠO VÀ LOAD MÔ HÌNH
# ==============================
print("⌛ Đang tải mô hình từ ổ cứng...")
text_model = SentenceTransformer(TEXT_MODEL_PATH)       # Tải mô hình văn bản vào bộ nhớ từ đường dẫn cục bộ
image_model_local = SentenceTransformer(IMAGE_MODEL_PATH) # Tải mô hình hình ảnh vào bộ nhớ (dùng SentenceTransformer để ổn định)

# Kết nối tới Database Milvus
milvus_client = MilvusClient(uri="http://localhost:19530") # Khởi tạo kết nối tới server Milvus qua cổng mặc định
COLLECTION_NAME = "ThucTap_image"                          # Tên bảng (collection) lưu trữ vector trong Milvus

# ============================================================
# 3. CẤU HÌNH NGƯỠNG TƯƠNG ĐỒNG (THRESHOLD) RIÊNG BIỆT
# ============================================================
IMAGE_THRESHOLD = 0.75  # Ngưỡng cao (khắt khe) cho tìm bằng ảnh: đảm bảo sản phẩm trả về phải rất giống về thị giác
TEXT_THRESHOLD = 0.24   # Ngưỡng thấp (nới lỏng) cho tìm bằng chữ: phù hợp với ngữ nghĩa đa dạng của từ ngữ Tiếng Việt
# ============================================================

def search_text(query_text, top_k=12):
    """ Hàm tìm kiếm sản phẩm bằng từ khóa văn bản """
    if not query_text: return []                         # Nếu từ khóa rỗng thì trả về danh sách trống
    
    query_vector = text_model.encode(query_text).tolist() # Chuyển câu truy vấn thành Vector (dạng list) bằng mô hình Text

    results = milvus_client.search(                      # Thực hiện truy vấn trên Milvus
        collection_name=COLLECTION_NAME,                 # Chỉ định bảng cần tìm
        data=[query_vector],                             # Dữ liệu vector đầu vào
        limit=top_k,                                     # Số lượng kết quả tối đa muốn lấy
        output_fields=["product_id"]                     # Trả về ID sản phẩm
    )
    
    # Trả về kết quả sau khi đã lọc qua ngưỡng dành cho Văn bản (0.26)
    return _extract_ids_with_threshold(results, threshold=TEXT_THRESHOLD, mode="TEXT")

def search_image(image_file, top_k=12):
    """ Hàm tìm kiếm sản phẩm bằng hình ảnh upload lên """
    try:
        img = Image.open(image_file).convert("RGB")      # Mở file ảnh và chuyển sang hệ màu RGB chuẩn AI
        with torch.no_grad():                            # Tắt tính toán gradient để tiết kiệm RAM và tăng tốc
            query_vector = image_model_local.encode(img).tolist() # Chuyển ảnh thành Vector đặc trưng (Embedding)

        results = milvus_client.search(                  # Truy vấn tìm kiếm vector tương đồng trên Milvus
            collection_name=COLLECTION_NAME,             # Chỉ định bảng ảnh sản phẩm
            data=[query_vector],                         # Vector của ảnh người dùng upload
            limit=top_k,                                 # Lấy Top K kết quả tương đồng nhất
            output_fields=["product_id"]                 # Lấy Product ID tương ứng
        )
        
        # Trả về kết quả sau khi đã lọc qua ngưỡng dành cho Hình ảnh (0.75)
        return _extract_ids_with_threshold(results, threshold=IMAGE_THRESHOLD, mode="IMAGE")
    except Exception as e:                               # Xử lý nếu file ảnh lỗi hoặc không đọc được
        print(f"❌ Lỗi xử lý ảnh: {e}")                   # In lỗi ra màn hình console để debug
        return []                                        # Trả về danh sách trống nếu có lỗi xảy ra

def _extract_ids_with_threshold(results, threshold, mode):
    """ Hàm bổ trợ: Trích xuất ID và lọc bỏ kết quả không đạt ngưỡng """
    ids = []                                             # Khởi tạo danh sách chứa các ID hợp lệ
    if results and len(results) > 0:                     # Kiểm tra nếu Milvus có trả về kết quả
        print(f"\n--- [LOG {mode}] Kiểm tra ngưỡng {threshold} ---") # In log bắt đầu quá trình lọc
        for res in results[0]:                           # Duyệt qua từng kết quả trong danh sách trả về
            score = res.get("distance", 0)               # Lấy điểm tương đồng (Cosine Similarity)
            entity = res.get("entity", {})               # Lấy các thông tin metadata đi kèm (entity)
            pid = entity.get("product_id")               # Trích xuất Product ID từ entity
            
            if score >= threshold:                       # SO SÁNH SCORE VỚI NGƯỠNG TƯƠNG ỨNG (0.75 hoặc 0.26)
                if pid is not None:                      # Nếu có ID và vượt ngưỡng
                    try:
                        clean_id = int(float(pid))       # Ép kiểu PID sang số nguyên (để khớp với MySQL)
                        ids.append(clean_id)             # Thêm ID hợp lệ vào danh sách kết quả cuối cùng
                    except (ValueError, TypeError):      # Phòng trường hợp ID trong Milvus không phải là số
                        continue                         # Bỏ qua và xét tiếp phần tử sau
                print(f"✅ Giữ lại PID {pid} với Score: {score:.4f}") # In log các sản phẩm được giữ lại để theo dõi độ chính xác của ngưỡng
            else:
                # In ra log các sản phẩm bị loại bỏ để theo dõi độ chính xác của ngưỡng
                print(f"⚠️ Loại bỏ PID {pid} do Score thấp: {score:.4f} (Yêu cầu: {threshold})")
                
    return ids                                           # Trả về danh sách ID sạch đã qua lọc ngưỡng và ép kiểu



    """
Dưới đây là luồng hoạt động chi tiết của code:

1. Luồng khởi tạo (Setup)
  - Load mô hình AI: Thay vì tải từ Internet, code tải mô hình từ ổ cứng
    (TEXT_MODEL_PATH, IMAGE_MODEL_PATH). Điều này giúp hệ thống chạy offline và
    tốc độ khởi động nhanh hơn.
      - text_model: Dùng để hiểu tiếng Việt đa ngôn ngữ.
      - image_model_local: Dùng để trích xuất đặc trưng hình ảnh.
  - Kết nối Milvus: Thiết lập đường truyền tới server Milvus (đang chạy tại
    cổng 19530) để sẵn sàng truy vấn vector.

2. Luồng tìm kiếm bằng văn bản (search_text)
    1.  Chuyển đổi (Encoding): Khi người dùng nhập "Bàn gỗ sồi", mô hình text_model
        sẽ biến câu này thành một Vector (một dãy số dài đại diện cho ý nghĩa của
        câu đó).
    2.  Truy vấn (Search): Gửi vector này lên Milvus. Milvus sẽ so sánh vector này
        với hàng nghìn vector sản phẩm có sẵn trong bảng ThucTap_image.
    3.  Lọc kết quả: Gọi hàm bổ trợ _extract_ids_with_threshold với ngưỡng 0.26.

3. Luồng tìm kiếm bằng hình ảnh (search_image)
    1.  Tiền xử lý: Mở file ảnh người dùng upload, chuyển về hệ màu RGB để mô hình
        AI đọc được.
    2.  Trích xuất đặc trưng: Dùng mô hình CLIP (image_model_local) để biến hình ảnh
        thành một Vector.
    3.  Truy vấn: Milvus tìm những ảnh trong kho có vector "gần giống" nhất với
        vector ảnh upload.
    4.  Lọc kết quả: Gọi hàm bổ trợ _extract_ids_with_threshold với ngưỡng 0.75.

4. Luồng lọc và hậu xử lý (_extract_ids_with_threshold)
    Đây là bước quan trọng nhất để đảm bảo chất lượng kết quả trả về:
  - Lấy Score (Độ tương đồng): Milvus trả về mỗi kết quả kèm theo một con số
    (score). Số này càng cao tức là càng giống.
  - So sánh ngưỡng (Thresholding):
      - Tại sao Ảnh cần 0.75? Vì đặc trưng hình ảnh rất rõ ràng, nếu thấp
        hơn 0.75 thường là ảnh khác hoàn toàn.
      - Tại sao Chữ chỉ cần 0.26? Vì Tiếng Việt rất phong phú, từ ngữ có thể
        khác nhau nhưng cùng nghĩa, nên cần nới lỏng ngưỡng để không bỏ lỡ kết
        quả.
  - Ép kiểu dữ liệu: Chuyển product_id từ dạng chuỗi/số thực về Số nguyên
    (Integer) để bạn có thể dùng ID này truy vấn tiếp vào cơ sở dữ liệu MySQL
    lấy thông tin chi tiết (tên, giá, mô tả).

"""