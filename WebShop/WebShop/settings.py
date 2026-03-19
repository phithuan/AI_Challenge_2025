"""
Django settings for WebShop project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ======================
# SECURITY
# ======================

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key")

DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = ['*']

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# ======================
# APPLICATIONS
# ======================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'app',
    'widget_tweaks',
    'django.contrib.humanize',

    'django.contrib.sites', # cần cho allauth

    'allauth',
    'allauth.account',
    'allauth.socialaccount',

    'allauth.socialaccount.providers.google',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    # thêm dòng này
    'allauth.account.middleware.AccountMiddleware',

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'WebShop.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # nếu có folder templates ngoài
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'app.context_processors.cart_data',
                'app.context_processors.categories_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'WebShop.wsgi.application'

# ======================
# DATABASE
# ======================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'sale_tmdt',
        'USER': 'root',
        'PASSWORD': 'root',
        'HOST': 'localhost',
        'PORT': '3307',
    }
}

# ======================
# PASSWORD VALIDATION
# ======================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ======================
# INTERNATIONALIZATION
# ======================
# settings.py

LANGUAGE_CODE = 'vi-vn' # Thêm -vn cho rõ ràng

USE_I18N = True
USE_TZ = True

# Quan trọng: Tắt L10N để Django dùng cấu hình THOUSAND_SEPARATOR bên dưới
USE_L10N = False 

USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = ','  # Nếu bạn muốn 2,000,000
# THOUSAND_SEPARATOR = '.' # Nếu bạn muốn 2.000.000 theo kiểu VN

NUMBER_GROUPING = 3

# ======================
# STATIC & MEDIA
# ======================


STATIC_URL = '/static/'

# Chỉ dùng khi deploy (collectstatic)
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

# ======================
# DEFAULT PK
# ======================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SITE_ID = 1 # cần cho allauth
# ======================
# DJANGO ALLAUTH CONFIG
# ======================

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'   # BẮT BUỘC xác thực email
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
# ======================
# Cấu hình Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'turnthuan1@gmail.com' # Email của bạn
EMAIL_HOST_PASSWORD = 'zmru vtxj sbvi eyrh' # Mã 16 ký tự vừa tạo

# lấy lại mk
# URL redirect sau khi reset
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'

# DOMAIN (quan trọng để email hoạt động đúng)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# ======================
# MILVUS VECTOR SEARCH
# ======================
USE_MILVUS = True