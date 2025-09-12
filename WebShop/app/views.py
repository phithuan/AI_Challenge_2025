from django.shortcuts import render, get_object_or_404, redirect  # render: trả template, get_object_or_404: lấy object hoặc 404, redirect: chuyển hướng
from django.http import HttpResponse, JsonResponse  # HttpResponse đơn giản, JsonResponse nếu muốn trả JSON
from .models import Product, Customer, Order, OrderItem  # import rõ ràng các model bạn cần
from json import loads  # để parse JSON từ request.body nếu cần
from django.views.decorators.csrf import csrf_exempt  # để bỏ qua CSRF cho API (nếu cần)
import datetime  # để xử lý thời gian nếu cần
import json  # để xử lý JSON nếu cần
from django.shortcuts import render, redirect
from .forms import CreateUserForm
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

def register(request):
    form = CreateUserForm()
    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    context = {'form': form}
    return render(request, 'app/register.html', context)

def loginPage(request): # tạo hàm để đăng nhập
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username ,password=password)
        if user is not None:
            login(request, user)
            return redirect('home') #
        else: messages.info(request,'user or password not correct')
    context = {}
    return render(request, 'app/login.html', context)

def logoutPage(request):
    logout(request)
    return redirect('login')

# Trang chủ: liệt kê sản phẩm
def home(request):
    products = Product.objects.all()  # lấy tất cả sản phẩm từ DB
    context = {'product': products}  # gán vào context (key 'product' vì home.html đang dùng {% for item in product %})
    return render(request, 'app/home.html', context)  # render template với context


# Trang giỏ hàng
def cart(request):
    # Kiểm tra user đã đăng nhập hay chưa
    if request.user.is_authenticated:  # nếu đã đăng nhập (fix: trước đó bạn gõ 'ueser' bị sai)
        # Lấy hoặc tạo Customer gắn với User hiện tại (tránh lỗi khi chưa có Customer)
        customer, created = Customer.objects.get_or_create(
            user=request.user,  # liên kết với object User
            defaults={'name': request.user.get_full_name() or request.user.username, 'email': request.user.email}
        )
        # Lấy hoặc tạo Order chưa hoàn tất cho customer này
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        # Lấy các OrderItem liên quan (dùng select_related để giảm queries)
        items = order.orderitem_set.select_related('product').all()
    else:
        # Người dùng ẩn danh: dùng session hoặc trả rỗng (ở đây tạm trả rỗng để tránh crash)
        order = None  # đặt order = None để template không bị lỗi khi tham chiếu
        items = []  # danh sách item rỗng cho anonymous users

        # LƯU Ý: bạn có thể implement session-cart ở đây:
        # cart = request.session.get('cart', {})
        # sau đó chuyển cart dict -> items hiển thị tương tự

    context = {'items': items, 'order': order}  # đưa items và order vào context cho template sử dụng
    return render(request, 'app/cart.html', context)  # render trang cart


# Trang checkout
def checkout(request):
    # Kiểm tra user đã đăng nhập hay chưa
    if request.user.is_authenticated:  # nếu đã đăng nhập (fix: trước đó bạn gõ 'ueser' bị sai)
        # Lấy hoặc tạo Customer gắn với User hiện tại (tránh lỗi khi chưa có Customer)
        customer, created = Customer.objects.get_or_create(
            user=request.user,  # liên kết với object User
            defaults={'name': request.user.get_full_name() or request.user.username, 'email': request.user.email}
        )
        # Lấy hoặc tạo Order chưa hoàn tất cho customer này
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        # Lấy các OrderItem liên quan (dùng select_related để giảm queries)
        items = order.orderitem_set.select_related('product').all()
    else:
        # Người dùng ẩn danh: dùng session hoặc trả rỗng (ở đây tạm trả rỗng để tránh crash)
        order = None  # đặt order = None để template không bị lỗi khi tham chiếu
        items = []  # danh sách item rỗng cho anonymous users

        # LƯU Ý: bạn có thể implement session-cart ở đây:
        # cart = request.session.get('cart', {})
        # sau đó chuyển cart dict -> items hiển thị tương tự

    context = {'items': items, 'order': order}  # đưa items và order vào context cho template sử dụng
    return render(request, 'app/checkout.html', context)  # render template checkout

def updateItem(request):
    data = json.loads(request.body)  # parse JSON từ request body
    productId = data['productId']  # lấy productId từ data
    action = data['action']  # lấy action từ data
    customer = request.user.customer  # lấy customer từ user hiện tại (giả sử user đã đăng nhập)
    product = Product.objects.get(id=productId)  # lấy product từ DB
    order, created = Order.objects.get_or_create(customer=customer, complete=False)  # lấy hoặc tạo order chưa hoàn tất
    orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)  # lấy hoặc tạo order item (sản phẩm trong đơn hàng)
    if action == 'add':
        orderItem.quantity += 1  # tăng số lượng lên 1
    elif action == 'remove':
        orderItem.quantity -= 1  # giảm số lượng xuống 1
    elif action == 'delete':
        orderItem.quantity = 0  # đặt số lượng về 0 để xoá
    orderItem.save()  # lưu vào DB
    if orderItem.quantity <= 0:
        orderItem.delete()  # nếu số lượng <= 0 thì xoá item khỏi order
    return JsonResponse('Item was added', safe=False)  # trả JSON đơn giản để test

# Chi tiết sản phẩm (nên render template chi tiết chứ không chỉ HttpResponse)
def product_detail(request, pk):
    # Lấy product hoặc trả 404 nếu không tồn tại
    product = get_object_or_404(Product, pk=pk)  # tìm sản phẩm theo id
    # Bạn nên tạo template 'app/product_detail.html' và hiển thị thông tin product ở đó
    return render(request, 'app/product_detail.html', {'product': product})  # render template chi tiết


# Thêm vào giỏ hàng (đơn giản: hỗ trợ user đã đăng nhập và anonymous bằng session)
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)  # lấy sản phẩm, nếu không có -> 404

    # Nếu user đã đăng nhập: lưu vào Order/OrderItem trong DB
    if request.user.is_authenticated:
        # lấy hoặc tạo Customer
        customer, created = Customer.objects.get_or_create(
            user=request.user,
            defaults={'name': request.user.get_full_name() or request.user.username, 'email': request.user.email}
        )
        # lấy hoặc tạo Order chưa hoàn tất
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        # lấy hoặc tạo OrderItem cho product trong order
        order_item, created = OrderItem.objects.get_or_create(order=order, product=product, defaults={'quantity': 0})
        order_item.quantity = (order_item.quantity or 0) + 1  # tăng số lượng lên 1
        order_item.save()  # lưu vào DB
        # redirect về trang cart (hoặc trả JSON tuỳ nhu cầu)
        return redirect('cart')  # tên url 'cart' phải có trong urls.py của bạn

    # Nếu anonymous: lưu vào session (đơn giản, key là 'cart' chứa dict {product_id: qty})
    cart = request.session.get('cart', {})  # lấy giỏ từ session, nếu không có -> {}
    pid = str(product.id)  # key của product trong session nên là string
    cart[pid] = cart.get(pid, 0) + 1  # tăng số lượng hoặc đặt 1 nếu chưa có
    request.session['cart'] = cart  # lưu lại vào session
    request.session.modified = True  # đánh dấu session đã thay đổi để Django lưu
    return redirect('cart')  # chuyển về trang cart


# GHI CHÚ:
# - Đảm bảo trong urls.py bạn có tên đường dẫn 'cart', 'product_detail', 'add_to_cart' tương ứng.
# - Tạo template 'app/product_detail.html' để hiển thị chi tiết product (mình đã gọi render đến template đó).
# - Nếu muốn dùng session-cart cho anonymous, hãy ở cart() đọc request.session['cart'] và build items tương ứng.
# - Nếu bạn muốn API (AJAX) cho add_to_cart, có thể return JsonResponse thay vì redirect.
