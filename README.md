# WebShop – Demo Hệ thống Bán hàng

## Giới thiệu
Đây là một dự án **demo cơ bản** xây dựng hệ thống bán hàng trực tuyến bằng **Django + Bootstrap**.  
Mục tiêu chính không phải thương mại hóa mà là **thử nghiệm các tính năng AI** như:
- Chatbot hỗ trợ khách hàng.
- Tìm kiếm sản phẩm thông minh.
- Gợi ý sản phẩm tương đồng dựa trên ảnh.

## Tính năng đã có

- **Trang chủ**
  - Banner động (carousel slider) với hiệu ứng chữ.
  - Hiển thị sản phẩm dưới dạng card (ảnh, tên, mô tả, giá).
  - Hiệu ứng hover zoom ảnh sản phẩm.

- **Người dùng**
  - Đăng ký tài khoản.
  - Đăng nhập hệ thống.

- **Giỏ hàng & Thanh toán**
  - Thêm sản phẩm vào giỏ hàng.
  - Xem chi tiết giỏ hàng.
  - Tiến hành thanh toán.

- **Sản phẩm**
  - Xem chi tiết sản phẩm.
  - Phân loại sản phẩm theo danh mục.
  - Tìm kiếm sản phẩm theo tên.

- **Chatbot AI**
  - Bong bóng chatbot hiển thị trên mọi trang.
  - Người dùng có thể trò chuyện trực tiếp với chatbot.

- **Hệ thống quản lý dữ liệu**
  - Quản lý người dùng, sản phẩm, danh mục, đơn hàng, mô tả sản phẩm.
  - CSDL: SQLite3.

## Định hướng phát triển
Trong tương lai, hệ thống sẽ được mở rộng:
- 🤖 Chatbot nâng cao (dùng LLM, gợi ý sản phẩm cá nhân hóa).
- 🖼️ Tìm kiếm sản phẩm dựa trên **ảnh tương đồng AI**.
- 🛍️ Quản lý giỏ hàng, thanh toán cơ bản.
- 📊 Hệ thống gợi ý sản phẩm thông minh.

## 🛠️ Công nghệ sử dụng
- **Backend**: Django, Django REST Framework  
- **Frontend**: HTML, CSS (Bootstrap 5), JavaScript  
- **AI/ML**: HuggingFace Transformers, Milvus (cho vector search – tích hợp trong tương lai)  
- **Khác**: Python 3.10+, Virtualenv  

## Cài đặt & chạy thử
```bash
# Clone repo
git clone <repo-url>
cd WebShop

# Tạo và kích hoạt môi trường ảo
python -m venv venv
venv\Scripts\activate  # Windows

# Cài đặt package
pip install -r requirements.txt

# Chạy server
python manage.py runserver
