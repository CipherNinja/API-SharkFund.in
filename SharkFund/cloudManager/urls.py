from django.urls import path
from .views import (
    RegisterView, CustomTokenRefreshView,
    LoginView, ForgetPasswordView,
    VerifyOTPView, ResetPasswordView, 
    UserProfileView, TeamReferralStatsView,
    TransactionHistoryView, WithdrawalHistoryAPIView,
    CustomerProfileView, MyReferralsView,
    MonthlyIncomeView, PaymentScreenshotUploadView
)
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

urlpatterns = [
    
    # JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),

    # Authentication 
    path('api/v1/register/', RegisterView.as_view(), name='register'),
    path('api/v1/login/', LoginView.as_view(), name='login'),
    path('api/v1/forget-password/', ForgetPasswordView.as_view(), name='forget_password'),
    path('api/v1/verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
    path('api/v1/reset-password/', ResetPasswordView.as_view(), name='reset_password'),

    # Dashboard Data
    path('api/v1/profile/', UserProfileView.as_view(), name='user-profile'),
    path('api/v1/stats/', TeamReferralStatsView.as_view(), name='team-stats'),
    path('api/v1/transaction/history/', TransactionHistoryView.as_view(), name='transaction-history'),
    path('api/v1/withdrawal/history/', WithdrawalHistoryAPIView.as_view(), name='withdrawal-history'),
    path('api/v1/edit/information/', CustomerProfileView.as_view(), name='edit-profile'),
    path('api/v1/my-referrals/', MyReferralsView.as_view(), name='my-referrals'),
    path('api/v1/earnings/monthly/', MonthlyIncomeView.as_view(), name='monthly-income'),
    path('api/v1/payments/upload/',PaymentScreenshotUploadView.as_view(),name="upload-payment")
    
    
]
