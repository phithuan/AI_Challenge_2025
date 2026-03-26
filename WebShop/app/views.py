from django.shortcuts import render, get_object_or_404, redirect  # render: trả template, get_object_or_404: lấy object hoặc 404, redirect: chuyển hướng
from django.http import HttpResponse, JsonResponse
from django.urls import reverse  # HttpResponse đơn giản, JsonResponse nếu muốn trả JSON
from .models import Category, Product, Order, OrderItem  # import rõ ràng các model bạn cần
from json import loads  # để parse JSON từ request.body nếu cần
from django.views.decorators.csrf import csrf_exempt  # để bỏ qua CSRF cho API (nếu cần)
import datetime  # để xử lý thời gian nếu cần
import json  # để xử lý JSON nếu cần
from .forms import CreateUserForm
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

from django.core.mail import send_mail # để  Import gửi email
from django.conf import settings # để Import gửi email 


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

    
# # views.py
# from django.shortcuts import render
# from .models import Product, Category
from django.core.paginator import Paginator
from django.shortcuts import render
from .models import Product, Category


def products(request):

    # ================= DANH MỤC =================
    categories = Category.objects.filter(is_sub=False)

    # ================= QUERYSET GỐC =================
    queryset = Product.objects.all()

    # ================= GET PARAMS =================
    category_id = request.GET.get("category")
    sort = request.GET.get("sort")
    materials = request.GET.getlist("material")
    price = request.GET.get("price")

    # ================= FILTER CATEGORY =================
    if category_id:
        queryset = queryset.filter(category__id=category_id)

    # ================= FILTER MATERIAL =================
    if materials:
        queryset = queryset.filter(material__in=materials)

    # ================= FILTER PRICE =================
    if price:
        queryset = queryset.filter(price__lte=price)

    # ================= SORT =================
    if sort == "price_asc":
        queryset = queryset.order_by("price") # 

    elif sort == "price_desc":
        queryset = queryset.order_by("-price")

    elif sort == "name":
        queryset = queryset.order_by("name")

    else:
        queryset = queryset.order_by("-id")

    # ================= PAGINATION =================
    paginator = Paginator(queryset, 12)
    page = request.GET.get("page")
    products = paginator.get_page(page)

    # ================= MATERIAL LIST (CHO FILTER UI) =================
    materials_list = Product.objects.values_list("material", flat=True).distinct()

    context = {
        "products": products,
        "categories": categories,
        "materials": materials_list,
        "selected_materials": materials   # thêm dòng này fix nè
    }

    return render(request, "app/products.html", context)


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
        image_results = search_milvus(searched, top_k=12)
        print("Search text:", searched)
        print("Milvus results:", image_results)

        return render(
            request,
            'app/search.html',
            {"searched": searched, "keys": keys, "image_results": image_results}
        )

from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages

def registerPage(request):

    if request.user.is_authenticated:
        return redirect('home')

    form = CreateUserForm()

    if request.method == 'POST':
        form = CreateUserForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            # tạo link kích hoạt
            activation_link = request.build_absolute_uri(
                reverse('activate', args=[user.id])
            )

            subject = "Kích hoạt tài khoản WebShop"
            message = f"""Xin chào {user.username}, Vui lòng click link bên dưới để kích hoạt tài khoản:{activation_link}"""

            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False,
            )

            messages.success(request, "Đăng ký thành công! Kiểm tra email để kích hoạt.")
            return redirect('login')

        else:
            messages.error(request, "Đăng ký thất bại")

    context = {'form': form}
    return render(request, 'app/register.html', context)
        


def activate(request, user_id):# để kích hoạt gmail

    try:
        user = User.objects.get(id=user_id)
        user.is_active = True
        user.save()

        messages.success(request, "Tài khoản đã kích hoạt, bạn có thể đăng nhập.")
        return redirect('login')

    except User.DoesNotExist:
        messages.error(request, "Link kích hoạt không hợp lệ")
        return redirect('home')


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
    # 1. ❌ CHƯA LOGIN → CHẶN NGAY
    if not request.user.is_authenticated:
        return JsonResponse({
            'error': 'not_authenticated',
            'message': 'Bạn cần đăng nhập để thao tác giỏ hàng!'
        }, status=401)

    # 2. Parse dữ liệu JSON từ request
    data = json.loads(request.body)
    productId = data['productId']
    action = data['action']

    # 3. Lấy sản phẩm từ database
    product = Product.objects.get(id=productId)

    # 4. Lấy hoặc tạo Order (giỏ hàng) của user
    order, created = Order.objects.get_or_create(
        customer=request.user,
        complete=False
    )

    # 5. Lấy hoặc tạo OrderItem (sản phẩm trong giỏ)
    orderItem, created = OrderItem.objects.get_or_create(
        order=order,
        product=product,
        defaults={'quantity': 0}
    )

    # 6. Xử lý action
    if action == 'add':
        orderItem.quantity += 1  # tăng số lượng
    elif action == 'remove':
        orderItem.quantity -= 1  # giảm số lượng
    elif action == 'delete':
        orderItem.quantity = 0   # xoá luôn

    # 7. Lưu vào database
    orderItem.save()

    # 8. Nếu số lượng <= 0 thì xoá khỏi giỏ
    if orderItem.quantity <= 0:
        orderItem.delete()

    # 9. Trả kết quả về frontend
    return JsonResponse({
        'message': 'success'
    })

# Chi tiết sản phẩm (nên render template chi tiết chứ không chỉ HttpResponse)
def product_detail(request, pk):
    # Lấy product hoặc trả 404 nếu không tồn tại
    product = get_object_or_404(Product, pk=pk)  # tìm sản phẩm theo id
    # Bạn nên tạo template 'app/product_detail.html' và hiển thị thông tin product ở đó
    return render(request, 'app/product_detail.html', {'product': product})  # render template chi tiết


# Thêm vào giỏ hàng (đơn giản: hỗ trợ user đã đăng nhập và anonymous bằng session)
# Tìm đến hàm add_to_cart trong file views.py và thay thế bằng đoạn này:

def add_to_cart(request, pk):
    # 1. Kiểm tra đăng nhập
    if not request.user.is_authenticated:
        # Nếu chưa đăng nhập, gửi thông báo cảnh báo và chuyển hướng sang trang login
        messages.warning(request, "Vui lòng đăng nhập để thêm sản phẩm vào giỏ hàng!")
        return redirect('login') 

    # 2. Nếu đã đăng nhập, tiến hành lấy sản phẩm
    product = get_object_or_404(Product, pk=pk)

    # 3. Lấy hoặc tạo đơn hàng chưa hoàn tất (giỏ hàng) cho User này
    order, created = Order.objects.get_or_create(
        customer=request.user, 
        complete=False
    )

    # 4. Lấy hoặc tạo mục sản phẩm trong đơn hàng
    order_item, created = OrderItem.objects.get_or_create(
        order=order, 
        product=product, 
        defaults={'quantity': 0}
    )

    # 5. Tăng số lượng lên 1 và lưu vào Database
    order_item.quantity = (order_item.quantity or 0) + 1
    order_item.save()

    # 6. Gửi thông báo thành công và quay về trang giỏ hàng
    messages.success(request, f"Đã thêm '{product.name}' vào giỏ hàng thành công.")
    return redirect('cart')

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
def order_success(request, order_id):

    # ADMIN
    if request.user.is_staff:
        order = get_object_or_404(Order, id=order_id)
        template = "app/admin_order_detail.html"

    # USER
    else:
        order = get_object_or_404(Order, id=order_id, customer=request.user)
        template = "app/order_success.html"

    items = order.orderitem_set.all()
    shipping = ShippingAddress.objects.filter(order=order).first()

    context = {
        "order": order,
        "items": items,
        "shipping": shipping,
    }

    return render(request, template, context)


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
#from rag_utils import search_text  # ✅ hàm bạn đã viết sẵn D:\Big_project_2025\RAG_Milvus\rag_utils.py
from .rag_utils import search_text  # ✅ hàm bạn đã viết sẵn D:\Big_project_2025\WebShop\app\rag_utils.py
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
# def admin_dashboard(request):
#     return render(request, 'app/admin_dashboard.html')


@login_required
@user_passes_test(admin_check)
def admin_products(request):
    return render(request, 'app/admin_product.html')

@login_required
@user_passes_test(admin_check)
def admin_orders(request):
    return render(request, 'app/admin_orders.html')

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Category
from .forms import CategoryForm

@login_required
@user_passes_test(admin_check)
def admin_categories(request):
    # --- XỬ LÝ XÓA ---
    if request.method == 'POST' and 'delete_id' in request.POST:
        cat_id = request.POST.get('delete_id')
        category = get_object_or_404(Category, id=cat_id)
        category.delete()
        messages.success(request, f'Đã xóa danh mục "{category.name}" thành công!')
        return redirect('admin_categories')

    # --- XỬ LÝ LƯU (THÊM/SỬA) ---
    if request.method == 'POST' and 'save_category' in request.POST:
        cat_id = request.POST.get('cat_id')
        if cat_id: # Trường hợp Sửa
            instance = get_object_or_404(Category, id=cat_id)
            form = CategoryForm(request.POST, instance=instance)
        else: # Trường hợp Thêm mới
            form = CategoryForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Lưu danh mục thành công!')
            return redirect('admin_categories')
        else:
            messages.error(request, 'Có lỗi xảy ra, vui lòng kiểm tra lại form.')

    # --- HIỂN THỊ DANH SÁCH ---
    categories_list = Category.objects.all().order_by('-id')
    total_cats = categories_list.count()
    
    # Phân trang 10 cái/trang
    paginator = Paginator(categories_list, 10)
    page_number = request.GET.get('page')
    categories = paginator.get_page(page_number)
    
    # Form trống để render trong Modal
    form = CategoryForm()

    context = {
        'categories': categories,
        'form': form,
        'total_cats': total_cats,
    }
    return render(request, 'app/admin_categories.html', context)


# viết phần dashborad-admin----------------------------------------------------------------
# app/views.py
import json
from datetime import timedelta, datetime, time
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import F, Sum, Count, Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Order, OrderItem, Category


@login_required
@user_passes_test(admin_check)
def dashboard_data_api(request):
    valid_completed_orders = Order.objects.filter(
        complete=True,
        orderitem__isnull=False
    ).distinct()

    total_orders = valid_completed_orders.count()

    revenue = OrderItem.objects.filter(
        order__complete=True
    ).aggregate(
        total=Sum(F('quantity') * F('product__sale_price'))
    )['total'] or 0

    return JsonResponse({
        "total_orders": total_orders,
        "total_revenue": float(revenue)
    })

from django.db.models import F, Sum, FloatField, ExpressionWrapper

def admin_check(user):
    return user.is_staff
from django.db.models.functions import TruncDate
from django.utils import timezone

@login_required
@user_passes_test(admin_check)
def admin_dashboard(request):
    # 1. THỐNG KÊ CƠ BẢN
    # Lấy cả đơn complete=True (đã thu tiền) và có thể tính cả đơn mới (tùy bạn)
    # Ở đây tôi giữ nguyên complete=True theo ý bạn
    valid_orders = Order.objects.filter(complete=True, orderitem__isnull=False).distinct()
    
    total_orders = valid_orders.count()
    
    # Tính tổng doanh thu chính xác hơn
    revenue_dict = OrderItem.objects.filter(
        order__complete=True
    ).aggregate(
        total=Sum(F('quantity') * F('product__price'), output_field=FloatField())
    )
    total_revenue = revenue_dict['total'] or 0
    new_customers = User.objects.filter(is_staff=False).count()

    # 2. DỮ LIỆU BIỂU ĐỒ (Dùng TruncDate để DB tự gom nhóm, nhanh hơn 7 lần)
    seven_days_ago = timezone.now().date() - timedelta(days=6)
    
    # Truy vấn gom nhóm doanh thu theo ngày
    daily_revenue_query = OrderItem.objects.filter(
        order__complete=True,
        order__date_ordered__date__gte=seven_days_ago # Lọc 7 ngày gần đây
    ).annotate(
        order_date=TruncDate('order__date_ordered')
    ).values('order_date').annotate(
        daily_total=Sum(F('quantity') * F('product__price'))
    ).order_by('order_date')

    # Chuyển kết quả truy vấn thành dictionary để dễ map dữ liệu
    revenue_map = {item['order_date'].strftime("%d/%m"): item['daily_total'] for item in daily_revenue_query}

    chart_labels = []
    chart_data = []
    
    # Tạo danh sách 7 ngày đầy đủ (kể cả ngày doanh thu bằng 0)
    for i in range(6, -1, -1):
        d = (timezone.now().date() - timedelta(days=i)).strftime("%d/%m")
        chart_labels.append(d)
        chart_data.append(float(revenue_map.get(d, 0))) # Nếu ngày đó không có tiền thì để 0

    # 3. DANH MỤC & ĐƠN HÀNG GẦN ĐÂY
    top_categories = Category.objects.annotate(num_products=Count('products')).order_by('-num_products')[:4]
    
    # Lấy 5 đơn mới nhất (Tính cả đơn đang chờ xử lý để Admin thấy ngay)
    recent_orders = Order.objects.filter(
        orderitem__isnull=False
    ).distinct().order_by('-date_ordered')[:5]

    context = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'new_customers': new_customers,
        'top_categories': top_categories,
        'recent_orders': recent_orders,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'app/admin_dashboard.html', context)

# HÀM QUẢN LÝ USER
@login_required
@user_passes_test(admin_check)
def admin_users(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'app/admin_users.html', {'users': users})


# viết phần admin_products-------------------------------------------------------------------------------
import csv
from django.http import HttpResponse
from django.core.paginator import Paginator as DjangoPaginator
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test

# Đảm bảo bạn đã import đầy đủ các Model và Form cần thiết
from .models import Product, Category, ProductImage
from .forms import ProductForm


# Hàm kiểm tra quyền admin (nếu chưa có thì để nguyên)
def admin_check(user):
    return user.is_staff

import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.text import get_valid_filename # Thêm cái này để xử lý tên file
import os
import csv
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.text import get_valid_filename
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator as DjangoPaginator
from django.db.models import Q
from django.http import HttpResponse

# Import Models và Forms của bạn
from .models import Product, Category, ProductImage
from .forms import ProductForm
from django.utils.text import slugify, get_valid_filename # Thêm slugify để tạo tên thư mục

# Hàm kiểm tra quyền Admin
def admin_check(user):
    return user.is_staff

@login_required
@user_passes_test(admin_check)
def admin_products(request):
    """
    Hàm quản lý sản phẩm tập trung: Liệt kê, Thêm, Sửa, Xóa và Xuất Excel.
    Xử lý lưu trữ file vật lý cho Model dùng CharField.
    """
    action = request.GET.get('action')
    product_id = request.GET.get('id')

    # ====================================================
    # 1. XỬ LÝ XÓA SẢN PHẨM
    # ====================================================
    if action == 'delete' and product_id:
        product = get_object_or_404(Product, id=product_id)
        product.delete()
        messages.success(request, f'Đã xóa sản phẩm {product.name} thành công!')
        return redirect('admin_products')

    # ====================================================
    # 2. XỬ LÝ THÊM & SỬA SẢN PHẨM (Lưu file vào Static)
    # ====================================================
    if action in ['add', 'edit']:
        product = None
        if action == 'edit':
            product = get_object_or_404(Product, id=product_id)

        if request.method == 'POST':
            # Khởi tạo form với dữ liệu POST và FILES
            form = ProductForm(request.POST, request.FILES, instance=product) if product else ProductForm(request.POST, request.FILES)
            
            # Trong hàm admin_products của views.py
            if form.is_valid():
                # Bước 1: Lấy instance nhưng chưa lưu (commit=False)
                product_instance = form.save(commit=False)

                # Đường dẫn gốc đến thư mục static của bạn
                base_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'images')

                # --- XỬ LÝ ẢNH CHÍNH ---
                if 'image' in request.FILES:
                    myfile = request.FILES['image']
                    clean_name = get_valid_filename(myfile.name)
                    
                    main_dir = os.path.join(base_path, 'main')
                    if not os.path.exists(main_dir): os.makedirs(main_dir)
                    
                    fs = FileSystemStorage(location=main_dir)
                    filename = fs.save(clean_name, myfile)
                    
                    # QUAN TRỌNG: Lưu "main/tên_file" vào Database
                    product_instance.image = f"main/{filename}"
                
                # Bước 2: Lưu Product vào DB
                product_instance.save()
                form.save_m2m()

                # --- XỬ LÝ ẢNH PHỤ ---
                import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.text import slugify, get_valid_filename # Thêm slugify để tạo tên thư mục
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Product, ProductImage
from .forms import ProductForm

@login_required
@user_passes_test(admin_check)
def admin_products(request):
    action = request.GET.get('action')
    product_id = request.GET.get('id')

    if action == 'delete' and product_id:
        product = get_object_or_404(Product, id=product_id)
        product.delete()
        messages.success(request, 'Đã xóa sản phẩm thành công!')
        return redirect('admin_products')

    if action in ['add', 'edit']:
        product = None
        if action == 'edit':
            product = get_object_or_404(Product, id=product_id)

        if request.method == 'POST':
            form = ProductForm(request.POST, request.FILES, instance=product) if product else ProductForm(request.POST, request.FILES)
            
            if form.is_valid():
                # 1. Lưu tạm để lấy tên sản phẩm tạo thư mục (Slug)
                product_instance = form.save(commit=False)
                # Tạo slug từ tên sản phẩm (VD: "Ghế Sofa" -> "ghe-sofa")
                product_slug = slugify(product_instance.name) 

                # Đường dẫn gốc: D:\Big_project_2025\WebShop\app\static\images
                base_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'images')

                # --- XỬ LÝ ẢNH CHÍNH (Lưu vào main/slug/file) ---
                if 'image' in request.FILES:
                    myfile = request.FILES['image']
                    clean_name = get_valid_filename(myfile.name)
                    
                    # Thư mục đích: static/images/main/ghe-sofa/
                    main_dir = os.path.join(base_path, 'main', product_slug)
                    if not os.path.exists(main_dir): os.makedirs(main_dir)
                    
                    fs = FileSystemStorage(location=main_dir)
                    filename = fs.save(clean_name, myfile)
                    
                    # Lưu vào DB đường dẫn giống SQL bạn chèn: "main/ghe-sofa/anh.jpg"
                    product_instance.image = f"main/{product_slug}/{filename}"
                
                product_instance.save()
                form.save_m2m()

                # --- XỬ LÝ NHIỀU ẢNH PHỤ (Lưu vào multiple/slug/file) ---
                if 'images' in request.FILES:
                    gallery_files = request.FILES.getlist('images')
                    # Thư mục đích: static/images/multiple/ghe-sofa/
                    gallery_dir = os.path.join(base_path, 'multiple', product_slug)
                    if not os.path.exists(gallery_dir): os.makedirs(gallery_dir)
                    
                    fs_gallery = FileSystemStorage(location=gallery_dir)
                    for f in gallery_files:
                        clean_f_name = get_valid_filename(f.name)
                        saved_f_name = fs_gallery.save(clean_f_name, f)
                        
                        # Lưu vào DB giống SQL: "multiple/ghe-sofa/anh_gallery.jpg"
                        ProductImage.objects.create(
                            product=product_instance, 
                            image=f"multiple/{product_slug}/{saved_f_name}"
                        )

                messages.success(request, 'Lưu thành công!')
                return redirect('admin_products')
        else:
            form = ProductForm(instance=product) if product else ProductForm()

        return render(request, 'app/admin_product_form.html', {'form': form, 'action': action})

    # ====================================================
    # 3. GIAO DIỆN DANH SÁCH (Tìm kiếm, Lọc, Phân trang)
    # ====================================================
    products_list = Product.objects.all().order_by('-id')

    # Xử lý tìm kiếm theo tên hoặc chất liệu
    query = request.GET.get('q')
    if query:
        products_list = products_list.filter(
            Q(name__icontains=query) | Q(material__icontains=query)
        )

    # Lọc theo danh mục (slug)
    category_slug = request.GET.get('category')
    if category_slug:
        products_list = products_list.filter(category__slug=category_slug)

    # Xử lý xuất Excel (CSV)
    if request.GET.get('export') == 'excel':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
        response.write(u'\ufeff'.encode('utf8')) # Hỗ trợ tiếng Việt CSV
        writer = csv.writer(response)
        writer.writerow(['ID', 'Tên sản phẩm', 'Giá bán', 'Chất liệu'])
        for p in products_list:
            writer.writerow([p.id, p.name, p.price, p.material])
        return response

    # Phân trang (10 sản phẩm mỗi trang)
    paginator = DjangoPaginator(products_list, 10)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)

    # Lấy danh sách danh mục để hiện lên bộ lọc
    categories = Category.objects.filter(is_sub=False)

    context = {
        'products': products,
        'categories': categories,
        'query': query,
        'current_category': category_slug,
    }
    return render(request, 'app/admin_product.html', context)


# tiếp tục làm phần đơn hàng admin----------------------------------------------------------------------
import csv
from django.http import HttpResponse
from django.core.paginator import Paginator as DjangoPaginator
from django.db.models import F, Sum, Q, Count  # Thêm Count ở đây
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test


# Giả sử hàm admin_check đã được định nghĩa ở trên
# from .models import Order, OrderItem

@login_required
@user_passes_test(lambda u: u.is_superuser)  # Đảm bảo hàm check admin của bạn gọi đúng
def admin_orders(request):
    # 1. XỬ LÝ CẬP NHẬT TRẠNG THÁI ĐƠN HÀNG (Nút Update Status)
    if request.method == 'POST' and 'update_status' in request.POST:
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, id=order_id)
        # Đảo ngược trạng thái
        order.complete = not order.complete
        order.save()
        status_text = "Hoàn tất" if order.complete else "Chờ xử lý"
        messages.success(request, f'Đã cập nhật đơn hàng #ORD-{order.id} thành "{status_text}"!')
        return redirect('admin_orders')

    # -------------------------------------------------------------------
    # BƯỚC SỬA LỖI CHÍNH Ở ĐÂY:
    # Lọc ra Queryset cơ sở: Chỉ lấy các Order có chứa ít nhất 1 OrderItem
    # -------------------------------------------------------------------
    valid_orders_qs = Order.objects.annotate(item_count=Count('orderitem')).filter(item_count__gt=0)

    # Gán vào orders_list để xử lý tiếp (sắp xếp mới nhất lên đầu)
    orders_list = valid_orders_qs.order_by('-date_ordered')

    # 2. XỬ LÝ TÌM KIẾM
    query = request.GET.get('q')
    if query:
        val = query.replace('#ORD-', '').strip()
        if val.isdigit():
            orders_list = orders_list.filter(id=val)
        else:
            orders_list = orders_list.filter(
                Q(customer__username__icontains=query) |
                Q(customer__email__icontains=query)
            )

    # 3. XỬ LÝ LỌC THEO TRẠNG THÁI (Tabs)
    status_filter = request.GET.get('status')
    if status_filter == 'completed':
        orders_list = orders_list.filter(complete=True)
    elif status_filter == 'pending':
        orders_list = orders_list.filter(complete=False)

    # Tính tổng tiền cho từng đơn hàng hiển thị
    for order in orders_list:
        order.calculated_total = sum(
            [item.product.price * item.quantity for item in order.orderitem_set.all() if item.product])

    # 4. XỬ LÝ XUẤT EXCEL (CSV)
    if request.GET.get('export') == 'excel':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders_export.csv"'
        response.write(u'\ufeff'.encode('utf8'))
        writer = csv.writer(response)

        writer.writerow(['Mã ĐH', 'Khách hàng', 'Email', 'Ngày đặt', 'Tổng tiền ($)', 'Trạng thái'])
        for o in orders_list:
            status = "Hoàn tất" if o.complete else "Chờ xử lý"
            cus_name = o.customer.username if o.customer else "Khách ẩn danh"
            cus_email = o.customer.email if o.customer else "N/A"
            date_str = o.date_ordered.strftime("%d/%m/%Y %H:%M") if o.date_ordered else ""
            writer.writerow([f"#ORD-{o.id}", cus_name, cus_email, date_str, o.calculated_total, status])
        return response

    # 5. THỐNG KÊ NHANH (STATS SUMMARY) - Sửa lại để không đếm giỏ hàng rỗng
    total_orders = valid_orders_qs.count()
    pending_orders = valid_orders_qs.filter(complete=False).count()
    completed_orders = valid_orders_qs.filter(complete=True).count()

    # Doanh thu (Chỉ tính những đơn complete=True)
    try:
        revenue_dict = OrderItem.objects.filter(order__complete=True).aggregate(
            total_revenue=Sum(F('quantity') * F('product__price'))
        )
        total_revenue = revenue_dict['total_revenue'] or 0
    except:
        total_revenue = 0

    # 6. PHÂN TRANG (10 đơn / trang)
    paginator = DjangoPaginator(orders_list, 10)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)

    context = {
        'orders': orders,
        'query': query,
        'status_filter': status_filter,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'total_revenue': total_revenue,
    }
    return render(request, 'app/admin_orders.html', context)

#viết tiếp trang quản lý user
# app/views.py
from django.contrib.auth.models import User
from django.utils import timezone


@login_required
@user_passes_test(admin_check)
def admin_users(request):
    # 1. Xử lý tìm kiếm người dùng
    query = request.GET.get('q', '')
    users_list = User.objects.all().order_by('-date_joined')

    if query:
        users_list = users_list.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        )

    # 2. Xử lý thao tác Xóa (Đã bỏ quyền cấp Admin cho khách)
    action = request.GET.get('action')
    target_id = request.GET.get('id')
    if action == 'delete' and target_id:
        user_target = get_object_or_404(User, id=target_id)
        # Bảo vệ Superuser không bị xóa từ giao diện này
        if user_target.is_superuser:
            messages.error(request, "Không thể xóa tài khoản Superuser hệ thống.")
        else:
            user_target.delete()
            messages.success(request, "Đã xóa người dùng thành công.")
        return redirect('admin_users')

    # 3. Thống kê nhanh cho Dashboard con
    total_users = User.objects.count()
    staff_count = User.objects.filter(is_staff=True).count()
    new_today = User.objects.filter(date_joined__date=timezone.now().date()).count()

    # 4. Phân trang (10 người dùng mỗi trang)
    paginator = DjangoPaginator(users_list, 10)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)

    context = {
        'users': users,
        'query': query,
        'total_users': total_users,
        'staff_count': staff_count,
        'new_today': new_today,
    }
    return render(request, 'app/admin_users.html', context)

# tiếp tục làm phần admin liên hệ----------------------------------------------------------------------
# app/views.py
@login_required
@user_passes_test(admin_check)
def admin_contact(request):
    # Giả sử bạn có model ContactMessage, nếu chưa có bạn có thể tạo sau.
    # Ở đây mình xử lý logic tìm kiếm và hiển thị cơ bản.
    query = request.GET.get('q', '')

    # Logic thống kê nhanh
    total_messages = 45  # Giả lập dữ liệu
    pending_reply = 12

    context = {
        'query': query,
        'total_messages': total_messages,
        'pending_reply': pending_reply,
        'admin_address': "Nguyễn Văn Cừ, Cái Khế, Cần Thơ",  # Địa chỉ của bạn
    }
    return render(request, 'app/admin_contact.html', context)