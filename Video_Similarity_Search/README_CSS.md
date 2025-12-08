# Video Similarity Search – AI Challenge 2025

Một pipeline tìm kiếm video theo nội dung văn bản, sử dụng mô hình CLIP và hệ thống quản lý vector (Milvus), kết hợp xử lý thời gian → frame index để đáp ứng yêu cầu chấm điểm Textual-KIS.

---

##  Pipeline tổng quan

### 1. Mã hóa văn bản (Text Encoding)
- Dùng mô hình **CLIP** để trích xuất embedding từ câu truy vấn (`encode_text`).
- Chuẩn hóa vector embedding (L2 normalization) để dễ dàng so sánh cosine similarity.

### 2. Tìm kiếm tương đồng (Similarity Search)
- Truy vấn embedding vào **Milvus** (vector database).
- Lấy về TOP-K kết quả tương đồng, mỗi kết quả gồm đường dẫn đến khung ảnh (frame).

### 3. Truy vấn metadata (PostgreSQL)
- Dùng `frame_path` từ kết quả Milvus để truy vấn thông tin:
  - `video_path`
  - `title`
  - `pts_time` (timestamp trong video)
- Kết quả được nhóm theo `video_path` để gom các timestamps cùng video.

### 4. Gom nhóm theo thời gian (Time Ranges)
- Dùng hàm `group_timestamps`:
  - Input: list các `pts_time` (đơn vị giây).
  - Nhóm các timestamp gần nhau (cách nhau ≤ threshold, ví dụ 10s) thành một khoảng `[start, end]`.
- Format mỗi khoảng thành chuỗi `"mm:ss"` để hiển thị dễ đọc.

### 5. Xuất kết quả (Readable Format)
- Kết quả trả về dạng:
  ```text
  Video: L21_V001.mp4
  Xuất hiện từ 6:02 đến 6:10
  Xuất hiện từ 17:11 đến 17:49

### 6. Tương tác thời gian → Frame Index (Textual-KIS Submission)

* Dùng thêm hàm `get_frame_idx_from_time` (dựa vào CSV metadata):

  * Chuyển `"mm:ss"` → số giây.
  * Dựa vào dữ liệu `pts_time` – `frame_idx`, làm **nội suy** tuyến tính để tìm frame gần nhất.
  * Output chuẩn: `<video_name>, <frame_idx>` — đúng định dạng yêu cầu cho Textual-KIS.

---

## Cấu trúc thư mục

```
Video_Similarity_Search/
├── final_model.ipynb   # Notebook chính chứa pipeline
├── data/
│   ├── video/          # Các video nguồn
│   └── csv/            # Các file metadata video như L21_V002.csv
├── README.md           # (Bạn đang xem)
└── requirements.txt    # Các thư viện phụ thuộc (pandas, numpy, milvus-client, psycopg2, torch, transformers…)
```


