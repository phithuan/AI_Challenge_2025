from django.contrib import admin
from .models import *

# =========================
# Inline ảnh phụ cho Product
# =========================
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3   # Hiển thị sẵn 3 ô upload ảnh phụ

# =========================
# Custom Product Admin
# =========================
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]

# =========================
# Register Models
# =========================
admin.site.register(Category)
admin.site.register(Product, ProductAdmin)  # 👈 Quan trọng
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(ShippingAddress)