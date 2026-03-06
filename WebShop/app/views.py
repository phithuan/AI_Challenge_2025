from django.shortcuts import render, get_object_or_404, redirect  # render: trả template, get_object_or_404: lấy object hoặc 404, redirect: chuyển hướng
from django.http import HttpResponse, JsonResponse  # HttpResponse đơn giản, JsonResponse nếu muốn trả JSON
from .models import Category, Product, Order, OrderItem  # import rõ ràng các model bạn cần
from json import loads  # để parse JSON từ request.body nếu cần
from django.views.decorators.csrf import csrf_exempt  # để bỏ qua CSRF cho API (nếu cần)
import datetime  # để xử lý thời gian nếu cần
import json  # để xử lý JSON nếu cần
from django.shortcuts import render, redirect
from .forms import CreateUserForm
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages


def category(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category)
    categories = Category.objects.filter(is_sub=False)
    context = {
        'category': category,       # danh mục đang chọn
        'categories': categories,   # list để render dropdown
        'products': products        # sản phẩm theo danh mục
    }
    return render(request, 'app/category.html', context)


from django.shortcuts import render, redirect
from django.db.models import Q
from .models import Product
from .milvus_utils import search_milvus

def search(request):
    if request.method == "POST":
        searched = request.POST["searched"]

        if not searched:
            return redirect('home')

        # Tách từ khóa
        keywords = searched.split()

        # Tạo truy vấn OR
        query = Q()
        for keyword in keywords:
            query |= Q(name__icontains=keyword)

        # Tìm trong DB
        keys = Product.objects.filter(query)

        # Tìm trong Milvus
        image_results = search_milvus(searched, top_k=6)

        return render(
            request,
            'app/search.html',
            {"searched": searched, "keys": keys, "image_results": image_results}
        )

# Đăng ký
def registerPage(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = CreateUserForm()

    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            user = form.save()   # 🔥 DÒNG QUAN TRỌNG NHẤT
            messages.success(request, 'Tạo tài khoản thành công')
            return redirect('login')
        else:
            messages.error(request, 'Đăng ký thất bại, kiểm tra lại thông tin')

    context = {'form': form}
    return render(request, 'app/register.html', context)


# Đăng nhập
def loginPage(request):
    # Nếu đã login rồi thì không cho vào lại trang login
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)              # 🔥 dòng quan trọng
            return redirect('home')           # home phải tồn tại trong urls
        else:
            messages.error(request, 'Sai username hoặc password')

    return render(request, 'app/login.html')


def logoutPage(request):
    logout(request)
    return redirect('login')

# Trang chủ: liệt kê sản phẩm
def home(request):
    products = Product.objects.all()[:12]  # lấy 12 sản phẩm
    context = { # đưa products và categorys vào context
        'product': products,
    }
    return render(request, 'app/home.html', context)


# Trang giỏ hàng
def cart(request):
    # Kiểm tra user đã đăng nhập hay chưa
    if request.user.is_authenticated:
        order, created = Order.objects.get_or_create(customer=request.user, complete=False)
        items = order.orderitem_set.select_related('product').all()
    else:
        order, items = None, []

    context = {'items': items, 'order': order}  # đưa items và order vào context cho template sử dụng
    return render(request, 'app/cart.html', context)  # render trang cart


# Trang checkout
def checkout(request): # trang thanh toán, hiển thị thông tin đơn hàng trước khi đặt hàng
    # Kiểm tra user đã đăng nhập hay chưa
    if request.user.is_authenticated:
        order, created = Order.objects.get_or_create(customer=request.user, complete=False)
        items = order.orderitem_set.select_related('product').all()
    else:
        order, items = None, []

    context = {'items': items, 'order': order}  # đưa items và order vào context cho template sử dụng
    return render(request, 'app/checkout.html', context)  # render template checkout

def updateItem(request):
    data = json.loads(request.body)  # parse JSON từ request body
    productId = data['productId']  # lấy productId từ data
    action = data['action']  # lấy action từ data
    product = Product.objects.get(id=productId)  # lấy product từ DB
    order, created = Order.objects.get_or_create(customer=request.user, complete=False)  # lấy hoặc tạo order chưa hoàn tất
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
        order, created = Order.objects.get_or_create(customer=request.user, complete=False)

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

from django.shortcuts import render, redirect, get_object_or_404
from .models import Order, OrderItem, ShippingAddress
from django.contrib.auth.decorators import login_required # để đảm bảo chỉ user đã đăng nhập mới được gọi

@login_required # đảm bảo chỉ user đã đăng nhập mới được gọi
def process_order(request):
    if request.method == "POST":
        # Lấy order chưa hoàn tất của user
        order, created = Order.objects.get_or_create(
            customer=request.user,
            complete=False
        )
        # =========================
        # LẤY PHƯƠNG THỨC THANH TOÁN
        # =========================
        payment_method = request.POST.get("payment_method")
        # =========================
        # LƯU ĐỊA CHỈ GIAO HÀNG
        # =========================
        ShippingAddress.objects.create(
            customer=request.user,
            order=order,
            address=request.POST.get('address'),
            city=request.POST.get('city'),
            state=request.POST.get('state'),
            mobile=request.POST.get('phone'),
        )
        # =========================
        # NẾU THANH TOÁN COD
        # =========================
        if payment_method == "cod":
            order.complete = True
            order.save()
            return redirect('order_success', order_id=order.id)
        # =========================
        # NẾU CHUYỂN KHOẢN
        # =========================
        if payment_method == "bank":
            return redirect('bank_payment', order_id=order.id)
    return redirect('checkout')

@login_required
def order_success(request, order_id): # nhận order_id từ URL để hiển thị thông tin đơn hàng vừa đặt thạnh công
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    items = order.orderitem_set.all()
    shipping = ShippingAddress.objects.filter(order=order).first()
    context = {
        "order": order,
        "items": items,
        "shipping": shipping,
    }
    return render(request, "app/order_success.html", context)


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Order  # đảm bảo import Order từ models.py

@csrf_exempt
def payment_webhook(request):
    if request.method != "POST":
        return JsonResponse({"status": "method not allowed"}, status=405)

    try:
        # In ra toàn bộ request để debug (xem terminal Django khi test)
        print("=== WEBHOOK NHẬN ĐƯỢC TỪ SEPAY ===")
        print("Headers:", request.headers)
        print("Body raw:", request.body)

        data = json.loads(request.body.decode('utf-8'))  # decode để tránh lỗi encoding
        print("Parsed JSON:", data)  # In JSON để xem fields thực tế

        # Lấy nội dung chuyển khoản – SePay dùng 'content' cho nội dung CK khách nhập
        content = data.get('content') or data.get('description') or ""
        content_upper = content.upper()

        # Chỉ xử lý nếu là giao dịch vào tiền ("in")
        if data.get('transferType') != 'in':
            print("Không phải giao dịch vào tiền, bỏ qua.")
            return JsonResponse({"status": "ignored_not_in"}, status=200)

        # Tìm "ORDER" trong nội dung
        if "ORDER" in content_upper:
            # Tách order_id: giả sử "ORDER123 abc" hoặc "Chuyen ORDER123"
            # Lấy phần sau "ORDER" đầu tiên, lấy số đầu tiên
            parts = content_upper.split("ORDER")
            if len(parts) > 1:
                # Lấy chuỗi sau ORDER, loại bỏ khoảng trắng, lấy phần số đầu
                after_order = parts[1].strip()
                order_id_str = ''.join([c for c in after_order.split()[0] if c.isdigit()])  # chỉ lấy số

                if order_id_str:
                    try:
                        order_id = int(order_id_str)
                        print(f"Phát hiện ORDER ID: {order_id}")

                        order = Order.objects.get(id=order_id)

                        # Kiểm tra số tiền khớp (tùy chọn nhưng rất khuyến khích để tránh fake)
                        transferred_amount = float(data.get('transferAmount') or data.get('amount') or 0)
                        cart_total = float(order.get_cart_total)

                        if abs(transferred_amount - cart_total) <= 1000:  # dung sai ±1000đ
                            if not order.complete:
                                order.complete = True
                                order.save()
                                print(f"ĐƠN HÀNG {order_id} ĐÃ COMPLETE THÀNH CÔNG!")
                                # Optional: gửi email xác nhận ở đây (dùng Django mail)
                        else:
                            print(f"Số tiền không khớp: chuyển {transferred_amount} nhưng đơn cần {cart_total}")

                    except ValueError:
                        print("Không parse được order_id thành số nguyên.")
                    except Order.DoesNotExist:
                        print(f"Không tìm thấy Order ID {order_id}")
                else:
                    print("Không tìm thấy số sau ORDER.")
            else:
                print("Không có 'ORDER' hợp lệ trong content.")
        else:
            print("Không có 'ORDER' trong nội dung chuyển khoản.")

        # Luôn trả 200 OK để SePay không retry
        return JsonResponse({"status": "ok"})

    except json.JSONDecodeError as e:
        print("Lỗi parse JSON:", str(e))
        return JsonResponse({"status": "invalid json"}, status=400)
    except Exception as e:
        print("Lỗi webhook:", str(e))
        return JsonResponse({"status": "error"}, status=500)


@login_required
def bank_payment(request, order_id): # nhận order_id để hiển thị thông tin đơn hàng trên trang thanh toán ngân hàng
    # Lấy order theo id
    order = get_object_or_404(
        Order,
        id=order_id,
        customer=request.user
    )
    context = {
        "order": order
    }
    return render(
        request,
        "app/bank_payment.html", # bạn cần tạo template này để hiển thị thông tin đơn hàng và hướng dẫn thanh toán
        context
    )


def check_order_status(request, order_id):
    try:
        order = Order.objects.get(id=order_id)

        return JsonResponse({
            "complete": order.complete
        })
    except Order.DoesNotExist:
        return JsonResponse({
            "complete": False
        })


def introduce(request):
    return render(request, 'app/introduce.html')


from django.http import JsonResponse # để trả JSON response
from django.views.decorators.csrf import csrf_exempt # để bỏ qua CSRF (nếu cần). cho phép frontend JS gọi API mà không cần CSRF token
import json # để parse JSON - đọc dữ liệu gửi từ chatbot.js
from rag_utils import search_text  # ✅ hàm bạn đã viết sẵn D:\Big_project_2025\RAG_Milvus\rag_utils.py

@csrf_exempt
def chatbot_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8")) # Đọc dữ liệu gửi từ chatbot.js 
            question = data.get("question", "") # Lấy câu hỏi từ data 
            if not question:
                return JsonResponse({"answer": "❌ Bạn chưa nhập câu hỏi"}, status=400)

            # Gọi Milvus RAG
            answer = search_text(question, top_k=1)

            return JsonResponse({"answer": answer}) # { "answer": "nội dung tìm được từ Milvus" }
        except Exception as e:
            return JsonResponse({"answer": f"❌ Lỗi server: {str(e)}"}, status=500)
    return JsonResponse({"answer": "❌ Chỉ hỗ trợ POST"}, status=405)


from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

def admin_check(user):
    return user.is_staff

@login_required
@user_passes_test(admin_check)
def admin_dashboard(request):
    return render(request, 'app/admin_dashboard.html')


@login_required
@user_passes_test(admin_check)
def admin_products(request):
    return render(request, 'app/admin_product.html')     

@login_required
@user_passes_test(admin_check)
def admin_orders(request):
    return render(request, 'app/admin_orders.html')     

@login_required
@user_passes_test(admin_check)
def admin_categories(request):
    return render(request, 'app/admin_categories.html')