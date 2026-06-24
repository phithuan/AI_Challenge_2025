# CUỘC THI AI Challenge 2025 - BÊN DƯỚI NỮA LÀ VỀ DỰ ÁN THỰC TẬP PHÁT TRIỂN LÊN CHAT BOT RAG
Tên đội: HTTA Legends Cuộc thi: AI Challenge 2025 – Thành phố Hồ Chí Minh
https://aichallenge.hochiminhcity.gov.vn/
## 🎬 Demo video  

[![Demo project video](https://img.youtube.com/vi/nWbh9e9vTbM/0.jpg)](https://www.youtube.com/watch?v=nWbh9e9vTbM)

**Hệ thống được tối ưu cho CLIP + Milvus, triển khai thực tế trên Google Cloud (Ubuntu Linux) do lượng dữ liệu rất lớn không thể .**
| Nội dung             | Chi tiết cuối cùng                                                                                                                             |
|----------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| **Mục đích**         | Xây dựng hệ thống Text-to-Video Retrieval: người dùng gõ tiếng Việt bất kỳ → trả về đúng video + đúng đoạn thời gian (giây) có nội dung đó      |
| **Bộ dữ liệu**       | ~500 video<br>Mỗi video 10–25 phút, 30 fps, đa chủ đề: nấu ăn, thể thao, thời sự, gameshow… |
| **Cấu trúc dữ liệu đầu vào** | • Video gốc: `/Videos/videos_Lxx/Lxx_Vyyy.mp4`<br>• Keyframes: `/Keyframes/keyframes_Lxx/Lxx_Vyyy/1.jpg … n.jpg`<br>• File CSV mapping cực kỳ quan trọng: `/map-keyframes/Lxx_Vyyy.csv`<br>  ↳ 4 cột: `n` (tên ảnh), `pts_time` (giây thực), `fps`, `frame_idx` (frame gốc) |
| **Hướng giải quyết** | 1. Encode toàn bộ keyframe bằng CLIP ViT-B/32 → vector 512-dim<br>2. Lưu vector + frame_path vào **Milvus 3.x** (COSINE index)<br>3. Lưu metadata (video_id, pts_time, frame_idx, milvus_id) vào **PostgreSQL**<br>4. Query: tiếng Việt → GoogleTranslator → Anh → CLIP text encoder → Milvus search → PostgreSQL lấy thời gian → group đoạn liên tục (gap ≤ 15s) |
| **Kết quả đạt được** | •Query tiếng Việt thuần: “ẾCH CHIÊN NƯỚC MẮN” → trả đúng 12 video, thời gian chính xác <br>• Tự động trả về ảnh keyframe minh họa |
| **nhược điểm**       | với dữ liệu cực kì lớn như thế có đôi lúc query không chính xác phải tìm lại thủ công -> mất thời gian |
| **cách khắc phục**       | Hybrid Search with BM25 có cố gắn thử nhưng chưa tối ưu thành công :(( |
| **kết quả cuộc thi**       | vào vòng bán kết, rất tiết nhưng có những trải nghiệm và kinh nghiệm rất đáng giá |


## Đóng Góp của tôi
* **Mã hóa & Lưu trữ Vector:**
    * Áp dụng mô hình **CLIP ViT-B/32** để mã hóa đồng nhất (512-dim) cả Keyframe (**Image** Encoder) và Văn bản truy vấn (**Text** Encoder).
    * Xây dựng hệ thống lưu trữ vector trên **Milvus 3.x** với **Docker**.
* **Quản lý Metadata**
    * Tích hợp **PostgreSQL** để lưu trữ và tra cứu metadata thời gian (`pts_time`, `video_id`).

**Thành viên**
* Trưởng nhóm: Vỏ Văn Tài **[Chi tiết dự án tại đây](https://github.com/taiiswibu/AI_challenge_HTTA)**
* Huỳnh Chí Phi Thuận
* Phan Nguyễn Vũ Huy
* Nguyễn Hoàng Ân

---
---
# AI Engineer Intern · AI-Powered E-Commerce Search & RAG Chatbot (Nội Thất PT)

## Demo Video

[![Demo Project Video](https://img.youtube.com/vi/ajCMvLVAvGE/0.jpg)](https://www.youtube.com/watch?v=ajCMvLVAvGE)
   
## Bài toán

Hệ thống tìm kiếm sản phẩm truyền thống dựa trên keyword matching gặp nhiều hạn chế khi dữ liệu sản phẩm tăng lớn:

* Không hiểu được ý nghĩa ngữ nghĩa của truy vấn.
* Không hỗ trợ tìm kiếm bằng hình ảnh.
* Dễ trả về kết quả rỗng khi tên sản phẩm và mô tả của người dùng khác nhau.
* Khó hỗ trợ tư vấn sản phẩm và giải đáp chính sách tự động.

## Giải pháp kỹ thuật

## 1. Multimodal Product Retrieval

Xây dựng hệ thống tìm kiếm đa phương thức cho phép:

* Text → Product Retrieval
* Image → Product Retrieval

Sử dụng CLIP để đưa hình ảnh và văn bản về cùng không gian embedding, cho phép truy xuất sản phẩm theo ngữ nghĩa thay vì khớp từ khóa.

## 2. Semantic Search Pipeline

Thiết kế pipeline xử lý dữ liệu sản phẩm:

* Chuẩn hóa dữ liệu sản phẩm từ JSON.
* Sinh `full_description` cho từng sản phẩm.
* Tách và chuẩn hóa dữ liệu chính sách từ các tài liệu Markdown.
* Chunking theo Heading + Recursive Text Splitting để giữ ngữ cảnh nghiệp vụ.

Embedding được tạo bằng:

* BGE-M3 (1024 dimensions)
* Ollama Local Embedding Service

Vector được lưu trữ trên:

* Milvus Vector Database
* HNSW Index
* COSINE Similarity Search

## 3. Retrieval-Augmented Generation (RAG)

Xây dựng chatbot RAG gồm các bước:

1. Intent Classification
2. Query Embedding
3. Vector Retrieval từ Milvus
4. Context Construction
5. LLM Response Generation

Hệ thống hỗ trợ 3 nhóm intent:

* `search_product`
* `search_policy`
* `answer_direct`

Cho phép chatbot vừa tìm kiếm sản phẩm vừa trả lời chính sách bảo hành, vận chuyển, đổi trả và tư vấn nội thất.

## 4. Hallucination Prevention & Guardrails

Triển khai nhiều cơ chế giảm hallucination:

* Retrieval chỉ sử dụng câu hỏi hiện tại, không dùng toàn bộ lịch sử hội thoại.
* Multi-turn conversation được xử lý bằng cách chỉ đưa 2 phản hồi assistant gần nhất vào prompt.
* Áp dụng similarity threshold để loại bỏ kết quả retrieval có độ liên quan thấp.
* Không cho phép LLM tự sinh tên sản phẩm, giá bán, kích thước hoặc chất liệu ngoài dữ liệu truy xuất.
* Cơ chế fallback khi không tìm thấy context phù hợp.

## 5. Server-Side Product Link Injection

Giải quyết lỗi LLM tạo sai URL sản phẩm:

* LLM chỉ sinh placeholder `[SP1]`, `[SP2]`, ...
* Backend ánh xạ placeholder với `product_id` thật từ metadata Milvus.
* Tự động inject link sản phẩm phía server.

Giúp loại bỏ hoàn toàn hiện tượng sinh sai URL hoặc điều hướng sai sản phẩm.

## Công nghệ sử dụng

* Python
* Django
* FastAPI
* Milvus
* Ollama
* BGE-M3
* CLIP
* Groq API (Llama 3.1 8B)
* Vector Search
* Retrieval-Augmented Generation (RAG)

## Kết quả

* Xây dựng thành công website nội thất tích hợp Multimodal Search và RAG Chatbot.
* Hỗ trợ tìm kiếm sản phẩm bằng văn bản và hình ảnh.
* Tìm kiếm theo ngữ nghĩa thay vì từ khóa chính xác.
* Giảm đáng kể hiện tượng hallucination thông qua retrieval guardrails và server-side link generation.
* Đạt ~92.9% tỷ lệ pass trên bộ kiểm thử RAG gồm 28 test case.



