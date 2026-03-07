# app/context_processors.py
from .models import Order, Category


def cart_data(request):
    """
    Context processor để đưa dữ liệu giỏ hàng (order + cart_items)
    vào tất cả template.
    """
    order = None
    cart_items = 0

    if request.user.is_authenticated:
        # 1. Lấy danh sách các giỏ hàng chưa hoàn tất, chọn cái đầu tiên tìm được
        order = Order.objects.filter(customer=request.user, complete=False).first()

        # 2. Nếu không tìm thấy giỏ hàng nào thì mới tạo mới
        if not order:
            order = Order.objects.create(customer=request.user, complete=False)

        # Gọi property trong model Order (tính tổng số lượng item trong giỏ)
        cart_items = order.get_cart_items

    return {
        'order': order,
        'cart_items': cart_items
    }


def categories_processor(request):
    """
    Context processor để lấy danh sách Category cha (is_sub=False)
    """
    categories = Category.objects.filter(is_sub=False)  # chỉ lấy danh mục cha
    return {'categories': categories}