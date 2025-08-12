from django.shortcuts import render
from django.http import HttpResponse  # Import lớp HttpResponse để trả về phản hồi HTTP từ
def home(request):
    return render(request, 'app/home.html')  # Trả về trang home.html

