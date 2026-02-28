from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # đặt luôn name để dễ gọi {% url 'home' %}
    path('register/', views.registerPage, name='register'), # trang đăng ký
    path('login/', views.loginPage, name='login'), # trang login
    path('logout/', views.logoutPage, name='logout'), 
    path('search/', views.search, name='search'), 
    path('category/<slug:slug>/', views.category, name='category'), # trang danh mục sản phẩm với slug của danh mục 
    path('cart/', views.cart, name='cart'), # trang giỏ hàng
    path('checkout/', views.checkout, name='checkout'), # trang thanh toán
    path('order_success/<int:order_id>/', views.order_success, name='order_success'), # trang thông báo đặt hàng thành công
    path('introduce/', views.introduce, name='introduce'), # trang giới thiệu


    path('update_item/', views.updateItem, name='update_item'), # cập nhật giỏ hàng

    # Thêm route chi tiết sản phẩm
    path('product/<int:pk>/', views.product_detail, name='product_detail'),

    # Thêm route thêm vào giỏ hàng
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),

    # API chatbot
    path("chatbot_api/", views.chatbot_api, name="chatbot_api"),

    # ✅ Xử lý thanh toán + thông báo
    path('process_order/', views.process_order, name='process_order'), # xử lý đơn hàng

    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'), # trang dashboard admin
    path('admin-products/', views.admin_products, name='admin_products'), # Thêm route quản lý sản phẩm
    path('admin-orders/', views.admin_orders, name='admin_orders'), # Thêm route quản lý đơn hàng
    path('admin-categories/', views.admin_categories, name='admin_categories'), # Thêm route quản lý danh mục
]
