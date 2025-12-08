# app/context_processors.py
from .models import Order

def cart_data(request):
    """
    Context processor để đưa dữ liệu giỏ hàng (order + cart_items)
    vào tất cả template.
    """
    order = None
    cart_items = 0

    if request.user.is_authenticated:
        # Lấy hoặc tạo giỏ hàng chưa hoàn tất cho user
        order, created = Order.objects.get_or_create(
            customer=request.user,
            complete=False
        )
        # Gọi property trong model Order (ví dụ get_cart_items)
        cart_items = order.get_cart_items  

    return {
        'order': order,
        'cart_items': cart_items
    }


from .models import Category
def categories_processor(request):
    categories = Category.objects.filter(is_sub=False)  # chỉ lấy danh mục cha
    return {'categories': categories}

