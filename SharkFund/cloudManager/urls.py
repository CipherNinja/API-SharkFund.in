from django.urls import path
from .views import RegisterView, CustomTokenRefreshView, LoginView, ForgetPasswordView, VerifyOTPView, ResetPasswordView, UserProfileView
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

urlpatterns = [
    path('api/v1/register/', RegisterView.as_view(), name='register'),
    path('api/v1/login/', LoginView.as_view(), name='login'),
    path('api/v1/forget-password/', ForgetPasswordView.as_view(), name='forget_password'),
    path('api/v1/verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
    path('api/v1/reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),

    # Dashboard Data
    path('api/v1/profile/', UserProfileView.as_view(), name='user-profile'),
    
]
