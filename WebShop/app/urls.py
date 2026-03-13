from django.urls import path
from . import views

urlpatterns = [
    # ==========================================
    # STORE PAGES & USER
    # ==========================================
    path('', views.home, name='home'),
    path('register/', views.registerPage, name='register'),
    path('login/', views.loginPage, name='login'),
    path('logout/', views.logoutPage, name='logout'),
    path('search/', views.search, name='search'),
    path('category/<slug:slug>/', views.category, name='category'),
    path('introduce/', views.introduce, name='introduce'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),

    # ==========================================
    # CART & CHECKOUT
    # ==========================================
    path('cart/', views.cart, name='cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('update_item/', views.updateItem, name='update_item'),
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('process_order/', views.process_order, name='process_order'),
    path('order_success/<int:order_id>/', views.order_success, name='order_success'),

    # ==========================================
    # API CHATBOT
    # ==========================================
    path("chatbot_api/", views.chatbot_api, name="chatbot_api"),

    # ==========================================
    # ADMIN SYSTEM
    # ==========================================
    # path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    # path('admin-products/', views.admin_products, name='admin_products'),
    # path('admin-orders/', views.admin_orders, name='admin_orders'),
    # path('admin-categories/', views.admin_categories, name='admin_categories'),
    path('admin-users/', views.admin_users, name='admin_users'),
    path('admin-contact/', views.admin_contact, name='admin_contact'),

    # ✅ Xử lý thanh toán + thông báo
    path('process_order/', views.process_order, name='process_order'), # xử lý đơn hàng

    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'), # trang dashboard admin
    path('admin-products/', views.admin_products, name='admin_products'), # Thêm route quản lý sản phẩm
    path('admin-orders/', views.admin_orders, name='admin_orders'), # Thêm route quản lý đơn hàng
    path('admin-categories/', views.admin_categories, name='admin_categories'), # Thêm route quản lý danh mục

    path('bank-payment/<int:order_id>/', views.bank_payment, name='bank_payment'), # Thêm route xử lý thanh toán qua ngân hàng

    
    path('bank-payment/<int:order_id>/', views.bank_payment, name='bank_payment'),

    path('payment-webhook/', views.payment_webhook, name="payment_webhook"),

    path('check-order/<int:order_id>/', views.check_order_status, name='check_order_status'),
    
    path('products/', views.products, name='products'),  # thêm dòng này

]
