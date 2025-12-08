# CUỘC THI AI Challenge 2025
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
##  Ứng Dụng Tiếp Theo: Vector Search trong E-commerce (Nội Thất PT)

Dựa trên kinh nghiệm xử lý dữ liệu lớn từ dự án **Text-to-Video Retrieval**, tôi nhận thấy tiềm năng giải quyết các vấn đề tìm kiếm sản phẩm trong thương mại điện tử bằng công nghệ **Vector Search**.

### 🔎 Vấn đề hiện tại khi tìm kiếm sản phẩm
* Khi người dùng gõ tên sản phẩm, nếu không khớp chuẩn xác — site thường trả về **không có kết quả**.
    * **Ví dụ:** tìm “bàn tròn gỗ ốc chó màu đen” sẽ không ra sản phẩm nếu tên sản phẩm là “Carolina Dining Table”.
* Tăng cảm giác khó chịu, trải nghiệm tìm kiếm kém khi dữ liệu sản phẩm lớn.

### 💡 Giải pháp: Kết hợp Vector Search (Semantic Search) với Milvus
* Biến tên và mô tả sản phẩm thành **embedding (vector)**.
* Khi user gõ query như “áo thun nam đẹp mặc hè”, hệ thống hiểu **ý nghĩa** (semantic), không chỉ khớp từ khóa — tìm ra sản phẩm phù hợp.
* Cải thiện đáng kể khả năng tìm kiếm: kể cả khi từ ngữ khác biệt, vẫn có thể tìm đúng sản phẩm.

### 🤖 Mở rộng: Chatbot hỗ trợ khách hàng
* Dựa trên embedding / semantic search: chatbot có thể đề xuất sản phẩm phù hợp, trả lời tự động các câu hỏi như “Cho mình áo thun nam thoáng mát mặc hè” → gợi ý sản phẩm.
* Cải thiện UX, giảm tải cho bộ phận hỗ trợ, tăng khả năng khách hàng tìm đúng món mình cần.
---
## kết quả

Xây dựng web bán sản phẩm nội thất thông minh cho cửa hàng Nội Thất PT (**Sử dụng Framework Django**):
* **Tìm sản phẩm bằng ảnh** (chụp/gửi ảnh → ra đúng món đồ).
* **Tìm sản phẩm bằng câu mô tả tự nhiên tiếng Việt** (dài, lủng củng, sai chính tả vẫn ra đúng).
* **Chatbot tự động tư vấn**, hiểu ý khách hàng ngay lập tức.
