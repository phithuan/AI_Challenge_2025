# app/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Product, Category

# ==========================================
# 0. CUSTOM WIDGET CHO NHIỀU ẢNH (DJANGO 5+)
# ==========================================
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

# ==========================================
# 1. FORM ĐĂNG KÝ TÀI KHOẢN (USER)
# ==========================================
class CreateUserForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

# ==========================================
# 2. FORM THÊM / SỬA SẢN PHẨM (PRODUCT)
# ==========================================
# app/forms.py
from django import forms
from .models import Product, Category, ProductImage

# Widget hỗ trợ chọn nhiều file cùng lúc
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

# Trường File hỗ trợ nhiều file
class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class ProductForm(forms.ModelForm):
    # 1. TRƯỜNG ẢNH CHÍNH: Ghi đè lại để thành FileInput (vì Model là CharField)
    # Tên field này trùng với tên field 'image' trong Model
    image = forms.ImageField(
        label="Ảnh chính sản phẩm",
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-primary hover:file:bg-orange-100'
        })
    )

    # 2. TRƯỜNG ẢNH PHỤ: Đây là trường bổ sung (không có trong model Product)
    # Chúng ta sẽ xử lý lưu vào model ProductImage ở views.py
    images = MultipleFileField(
        label="Bộ sưu tập ảnh phụ (Chọn nhiều ảnh)",
        required=False,
        widget=MultipleFileInput(attrs={
            'multiple': True,
            'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'
        })
    )

    class Meta:
        model = Product
        # Liệt kê các trường muốn xuất hiện trên form
        fields = [
            'name', 'price', 'sale_price', 'category', 'image', 
            'description', 'material', 'size', 'origin', 
            'quality', 'history'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Nhập tên sản phẩm...',
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
            }),
            'price': forms.NumberInput(attrs={
                'placeholder': 'Ví dụ: 1000000',
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
            }),
            'sale_price': forms.NumberInput(attrs={
                'placeholder': 'Giá sau khi giảm (nếu có)',
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
            }),
            'category': forms.SelectMultiple(attrs={
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary min-h-[120px]'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Mô tả ngắn gọn về sản phẩm...',
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
            }),
            'material': forms.TextInput(attrs={
                'placeholder': 'Ví dụ: Gỗ sồi, Da công nghiệp...',
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
            }),
            'size': forms.TextInput(attrs={
                'placeholder': 'Ví dụ: 1m6 x 2m',
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
            }),
            'origin': forms.TextInput(attrs={
                'placeholder': 'Ví dụ: Việt Nam, Italia...',
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
            }),
            'quality': forms.TextInput(attrs={
                'placeholder': 'Ví dụ: Loại 1, Cao cấp...',
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
            }),
            'history': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Thông tin lịch sử hoặc ghi chú thêm...',
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
            }),
        }

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        # Nếu đang Edit, trường image sẽ không bắt buộc (vì đã có ảnh cũ trong CharField)
        if self.instance and self.instance.pk:
            self.fields['image'].required = False

# ==========================================
# 3. FORM DANH MỤC (CATEGORY)
# ==========================================
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'is_sub', 'sub_category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary', 'placeholder': 'VD: Tủ lạnh...'}),
            'slug': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary', 'placeholder': 'VD: tu-lanh'}),
            'is_sub': forms.CheckboxInput(attrs={'class': 'rounded border-slate-300 text-primary focus:ring-primary'}),
            'sub_category': forms.Select(attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'}),
        }