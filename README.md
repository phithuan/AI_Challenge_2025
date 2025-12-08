# CUỘC THI AI Challenge 2025
Tên đội: HTTA Legends Cuộc thi: AI Challenge 2025 – Thành phố Hồ Chí Minh

Nhiệm vụ
Phát triển Hệ thống tìm bằng văn bản (Semantic Multimedia Search System), cho phép người dùng tìm ảnh, video.

Hệ thống được tối ưu cho CLIP + Milvus, triển khai thực tế trên Google Cloud (Ubuntu Linux).

Thành viên
Trưởng nhóm: Vỏ Văn Tài

Thành viên:

Huỳnh Chí Phi Thuận
Phan Nguyễn Vũ Huy
Nguyễn Hoàng Ân

## Mục tiêu dự án
Xây dựng hệ thống tìm kiếm sản phẩm nội thất cực kỳ thông minh cho cửa hàng Nội Thất PT:
- Tìm sản phẩm bằng ảnh (chụp/gửi ảnh → ra đúng món đồ)
- Tìm sản phẩm bằng câu mô tả tự nhiên tiếng Việt (dài, lủng củng, sai chính tả vẫn ra đúng)
- Chatbot tự động tư vấn 24/7, hiểu ý khách hàng ngay lập tức

→ Thay thế hoàn toàn tìm kiếm LIKE %% chậm chạp và “không hiểu ý”.

## Vấn đề cũ → Giải pháp mới

| Vấn đề cũ                              | Giải pháp mới (Vector + Milvus)                              | Kết quả thực tế đạt được                                      |
|----------------------------------------|---------------------------------------------------------------|----------------------------------------------------------------|
| Gõ “sofa góc chữ L trắng dưới 15tr” → 0 kết quả | Dùng CLIP + Milvus → tìm bằng ảnh hoặc text đều ra đúng sofa | Tìm đúng 100% dù tên sản phẩm không chứa từ khóa                |
| Khách gõ sai chính tả, lóng (“ghế công thai hoc”) → không ra | Dùng bge-m3 / all-MiniLM → hiểu ngữ nghĩa tiếng Việt         | Vẫn ra đúng ghế công thái học giá rẻ nhất                     |
| Tìm kiếm chậm khi có >10.000 sản phẩm  | Milvus IVF_FLAT / HNSW → <50ms với hàng triệu vector         | Tốc độ gần như tức thì                                        |
| Chatbot trả lời “không hiểu”           | RAG + Milvus → lấy đúng thông tin sản phẩm để trả lời        | Chatbot tư vấn như nhân viên thật                             |

## Kiến trúc hệ thống (tóm tắt trong 5 bước)

```mermaid
graph TD
    A[Ảnh sản phẩm + Mô tả] --> B(Sinh embedding)
    B -->|CLIP/CLIP| C{Milvus Vector DB}
    D[Câu hỏi khách / Ảnh khách gửi] --> E(Sinh embedding cùng model)
    E --> C
    C --> F[Top 3-5 sản phẩm phù hợp nhất + metadata]
    F --> G[Chatbot trả lời + hiển thị ảnh]