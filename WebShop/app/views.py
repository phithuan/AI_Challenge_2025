from django.shortcuts import render
from django.http import HttpResponse  # Dùng để trả phản hồi văn bản đơn giản
from .models import *  # Import tất cả các model từ models.py

# Trang chủ
def home(request):
    product = Product.objects.all()  # Lấy tất cả sản phẩm từ database
    context = {'product': product}  # Tạo một context chứa danh sách sản phẩm
    return render(request, 'app/home.html', context)  # Trả về template home.html
def cart(request):
    context = {}  # Tạo một context rỗng
    return render(request, 'app/cart.html', context)  # Trả về template cart.html
def checkout(request):
    context = {}  # Tạo một context rỗng
    return render(request, 'app/checkout.html', context)  # Trả về template checkout.html


# Chi tiết sản phẩm
def product_detail(request, pk):
    return HttpResponse(f"📦 Chi tiết sản phẩm có ID = {pk}")

# Thêm vào giỏ hàng
def add_to_cart(request, pk):
    return HttpResponse(f"🛒 Đã thêm sản phẩm có ID = {pk} vào giỏ hàng!")

