from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # đặt luôn name để dễ gọi {% url 'home' %}
    path('register/', views.register, name='register'), # trang đăng ký
    path('login/', views.loginPage, name='login'), # trang login
    path('logout/', views.logoutPage, name='logout'), 
    path('cart/', views.cart, name='cart'), # trang giỏ hàng
    path('checkout/', views.checkout, name='checkout'), # trang thanh toán  

    path('update_item/', views.updateItem, name='update_item'), # cập nhật giỏ hàng

    # Thêm route chi tiết sản phẩm
    path('product/<int:pk>/', views.product_detail, name='product_detail'),

    # Thêm route thêm vào giỏ hàng
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
]
