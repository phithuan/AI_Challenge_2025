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
class ProductForm(forms.ModelForm):
    # Đây là trường cho NHIỀU ảnh phụ
    images = forms.FileField(
        widget=MultipleFileInput(attrs={
            'multiple': True,
            'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
        }),
        required=False,
        label="Thêm ảnh phụ (Quét chuột hoặc giữ Ctrl để chọn nhiều ảnh)"
    )

    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(
                attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'}),
            'price': forms.NumberInput(
                attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'}),
            'description': forms.Textarea(
                attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary',
                       'rows': 4}),
            'category': forms.SelectMultiple(
                attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'}),
            'material': forms.TextInput(
                attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'}),
            'origin': forms.TextInput(
                attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'}),
            'quality': forms.TextInput(
                attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'}),
            'size': forms.TextInput(
                attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'}),
            'history': forms.Textarea(
                attrs={'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary',
                       'rows': 3}),

            # SỬA LỖI Ở ĐÂY: Khai báo rõ widget cho ảnh chính
            'image': forms.FileInput(attrs={
                'class': 'w-full rounded-xl border-slate-200 focus:ring-primary focus:border-primary'
            }),
        }

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