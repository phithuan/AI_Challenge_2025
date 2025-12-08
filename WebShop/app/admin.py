from django.contrib import admin
from .models import *  # Import all models

# Register your models here.
# admin.site.register(Customer)
admin.site.register(Category) 
admin.site.register(Product)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(ShippingAddress)
# Đăng ký các model để quản lý qua trang admin của Django