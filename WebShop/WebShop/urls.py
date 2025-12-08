"""
URL configuration for WebShop project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from django.conf.urls.static import static # import static để dùng static()
from django.conf import settings # import settings để dùng settings.MEDIA_URL và settings.MEDIA_ROOT

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),  # Thêm dòng này để bao gồm các URL từ app
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) # Thêm dòng này để phục vụ file media trong quá trình phát triển