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
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-products/', views.admin_products, name='admin_products'),
    path('admin-orders/', views.admin_orders, name='admin_orders'),
    path('admin-categories/', views.admin_categories, name='admin_categories'),
    path('admin-users/', views.admin_users, name='admin_users'),
    path('admin-contact/', views.admin_contact, name='admin_contact'),
]