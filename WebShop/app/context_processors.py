from .models import Order, Customer

def cart_data(request): # context processor để lấy dữ liệu giỏ hàng
    if request.user.is_authenticated:
        customer, created = Customer.objects.get_or_create(user=request.user)
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        cart_items = order.get_cart_items
    else: 
        order = None
        cart_items = 0

    return {'order': order, 'cart_items': cart_items} 
