from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator  # ✅ dùng validator cho số điện thoại
from django.contrib.auth.forms import UserCreationForm  # để làm việc với User

# Khách hàng
# class Customer(models.Model):
#     # Liên kết 1-1 với User trong Django, nếu user bị xóa thì set NULL
#     user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)  
#     name = models.CharField(max_length=200, null=True)  # Tên khách hàng
#     email = models.CharField(max_length=200, null=True)  # Email khách hàng
#     def __str__(self):
#         return str(self.name) if self.name else "Unnamed Customer" 

# danh mục Category
class Category(models.Model): # Mỗi danh mục có các thuộc tính sau
    sub_category = models.ForeignKey('self', on_delete=models.CASCADE, related_name='sub_categories', null=True, blank=True)
    is_sub = models.BooleanField(default=False) # Danh mục con hay không
    name = models.CharField(max_length=200, null=True)  # Tên danh mục
    slug = models.SlugField(max_length=200, unique=True)  # Slug cho URL thân thiện
    def __str__(self):
        return self.name # Hiển thị tên danh mục

# Sản phẩm
class Product(models.Model): # Mỗi sản phẩm có các thuộc tính sau
    name = models.CharField(max_length=200, null=True)  # Tên sản phẩm
    price = models.FloatField()  # Giá sản phẩm
    # ✅ THÊM GIÁ KHUYẾN MÃI
    sale_price = models.FloatField(null=True, blank=True)

    digital = models.BooleanField(default=False, null=True, blank=True)  # digital=True nghĩa là sản phẩm số (ví dụ: Ebook, phần mềm), không cần shipping
    
    image = models.CharField(max_length=255, null=True, blank=True)  # ảnh chính của sản phẩm

    category = models.ManyToManyField(Category, related_name='products')  # Danh mục cha
    description = models.TextField(null=True, blank=True)  # ✅ Thêm trường mô tả

    material = models.CharField(max_length=200, null=True, blank=True)   # chất liệu
    size = models.CharField(max_length=100, null=True, blank=True)       # kích thước
    origin = models.CharField(max_length=200, null=True, blank=True)     # xuất xứ
    quality = models.CharField(max_length=100, null=True, blank=True)    # chất lượng (Loại 1, VIP,…)
    history = models.TextField(null=True, blank=True)                    # lịch sử / thông tin thêm

    def __str__(self):
        return self.name # Hiển thị tên sản phẩm
    @property
    def ImageURL(self):
        if self.image: # Nếu self.image là "main/giuong.jpg" -> return "/static/images/main/giuong.jpg"
            # image trong DB đang lưu là: multiple/slug/ten_anh.jpg
            # Kết quả trả về: /static/images/multiple/slug/ten_anh.jpg
            return "/static/images/" + str(self.image)
        return "/static/app/images/no-image.png"  # fallback cho đẹp
    
    # ✅ TÍNH PHẦN TRĂM GIẢM
    @property
    def discount_percent(self):
        if self.sale_price and self.price:
            return round(100 - (self.sale_price / self.price * 100))
        return 0

    # ✅ GIÁ HIỂN THỊ (ưu tiên giá sale)
    @property
    def final_price(self):
        return self.sale_price if self.sale_price else self.price

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.CharField(max_length=255, null=True, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image of {self.product.name}"

    @property
    def ImageURL(self):
        if self.image: # Nếu self.image là "multiple/anh1.jpg" -> return "/static/images/multiple/anh1.jpg"
            return f"/static/images/{self.image}"
        return ""


# Đơn hàng
class Order(models.Model):
    # Mỗi đơn hàng thuộc về 1 khách hàng (Customer)
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  
    date_ordered = models.DateTimeField(auto_now_add=True)  # Thời điểm đặt hàng
    complete = models.BooleanField(default=False, null=True, blank=False)  # Đơn hàng đã hoàn tất chưa
    transaction_id = models.CharField(max_length=200, null=True)  # Mã giao dịch
    def __str__(self):
        return str(self.id)  # Hiển thị ID đơn hàng
    @property
    def get_cart_items(self):
        # Tổng số lượng sản phẩm
        orderitems = self.orderitem_set.all()
        total = sum([item.quantity for item in orderitems])
        return total
    @property
    def get_cart_total(self):
        # Tổng tiền
        orderitems = self.orderitem_set.all()
        total = sum([item.get_price_quantity for item in orderitems])
        return total

    @property
    def total_amount(self):
        orderitems = self.orderitem_set.all()
        total = sum([item.product.final_price * item.quantity for item in orderitems if item.product])
        return total


# Chi tiết từng sản phẩm trong đơn hàng
class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)  # Sản phẩm thuộc order
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)  # Đơn hàng nào chứa sản phẩm này
    quantity = models.IntegerField(default=0, null=True, blank=True)  # Số lượng
    date_added = models.DateTimeField(auto_now_add=True)  # Ngày thêm vào giỏ hàng
    @property
    def get_price_quantity(self):
        # Tổng tiền = giá * số lượng
        if self.product:
            return self.product.final_price * self.quantity
        return 0


# Địa chỉ giao hàng
class ShippingAddress(models.Model):
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  # Khách hàng nào
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
