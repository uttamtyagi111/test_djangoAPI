from django.contrib import admin
from django.urls import path
from .views import LogoutDeviceView
from . import views
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,)

urlpatterns = [
    path('register/', views.registerPage, name="register"),
    path('login/', views.loginPage, name="login"),
    path('logout/', views.logout_view, name='logout'),
    path('logout-device/', LogoutDeviceView.as_view(), name='logout-device'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify-otp/',views.verify_otp, name='verify_otp'),
    path('reset_password/', views.request_password_reset, name='password_reset'),
    path('reset_password/<uidb64>/<token>/', views.reset_password, name='password_reset_confirm'),
    path('home/', views.home, name="home"),
    path('users/', views.user_list, name='user_list'),
    path('devices/', views.get_logged_in_devices, name='get_logged_in_devices'),
    path('blacklisted-token/', views.check_blacklisted_token, name='check_blacklisted_token'),
]
