from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator  # ✅ dùng validator cho số điện thoại

# Khách hàng
class Customer(models.Model):
    # Liên kết 1-1 với User trong Django, nếu user bị xóa thì set NULL
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)  
    name = models.CharField(max_length=200, null=True)  # Tên khách hàng
    email = models.CharField(max_length=200, null=True)  # Email khách hàng
    def __str__(self):
        return self.name  # Hiển thị tên khách hàng


# Sản phẩm
class Product(models.Model):
    name = models.CharField(max_length=200, null=True)  # Tên sản phẩm
    price = models.FloatField()  # Giá sản phẩm
    digital = models.BooleanField(default=False, null=True, blank=True)  # digital=True nghĩa là sản phẩm số (ví dụ: Ebook, phần mềm), không cần shipping
    image = models.ImageField(null=True, blank=True)  # Ảnh sản phẩm
    def __str__(self):
        return self.name # Hiển thị tên sản phẩm
    @property
    def ImageURL(self): # Hàm lấy URL ảnh, nếu không có ảnh thì trả về chuỗi rỗng
        try:
            url = self.image.url
        except:
            url = ''
        return url


# Đơn hàng
class Order(models.Model):
    # Mỗi đơn hàng thuộc về 1 khách hàng (Customer)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)  
    date_ordered = models.DateTimeField(auto_now_add=True)  # Thời điểm đặt hàng
    complete = models.BooleanField(default=False, null=True, blank=False)  # Đơn hàng đã hoàn tất chưa
    transaction_id = models.CharField(max_length=200, null=True)  # Mã giao dịch
    def __str__(self):
        return str(self.id)  # Hiển thị ID đơn hàng


# Chi tiết từng sản phẩm trong đơn hàng
class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)  # Sản phẩm thuộc order
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)  # Đơn hàng nào chứa sản phẩm này
    quantity = models.IntegerField(default=0, null=True, blank=True)  # Số lượng
    date_added = models.DateTimeField(auto_now_add=True)  # Ngày thêm vào giỏ hàng


# Địa chỉ giao hàng
class ShippingAddress(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)  # Khách hàng nào
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)  # Đơn hàng nào
    address = models.CharField(max_length=200, null=True)  # Địa chỉ cụ thể
    city = models.CharField(max_length=200, null=True)  # Thành phố
    state = models.CharField(max_length=200, null=True)  # Tỉnh/Bang
    # ✅ Kiểm tra số điện thoại: phải bắt đầu bằng 0, có 10 chữ số
    mobile = models.CharField(
        max_length=10,
        validators=[RegexValidator(
            regex=r'^0\d{9}$',
            message="Số điện thoại phải bắt đầu bằng 0 và có đúng 10 chữ số"
        )],
        null=True,
        blank=True
    )
    date_added = models.DateTimeField(auto_now_add=True)  # Ngày mua hàng
    def __str__(self):
        return self.address
