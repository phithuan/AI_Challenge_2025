from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # đặt luôn name để dễ gọi {% url 'home' %}
    path('cart/', views.cart, name='cart'),
    path('checkout/', views.checkout, name='checkout'),

    # Thêm route chi tiết sản phẩm
    path('product/<int:pk>/', views.product_detail, name='product_detail'),

    # Thêm route thêm vào giỏ hàng
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
]
