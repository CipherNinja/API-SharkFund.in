from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics, permissions
from .serializers import (
    CustomUserSerializer, LoginSerializer,
    ForgetPasswordSerializer, VerifyOTPSerializer,
    ResetPasswordSerializer, UserProfileSerializer,
    TransactionHistorySerializer, WithdrawalHistorySerializer,
    CustomerProfileSerializer, ReferralSerializer,
    MonthlyIncomeSerializer
)

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Transaction, CustomUser, MonthlyIncome
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

class CustomTokenRefreshView(BaseTokenRefreshView):
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            return Response({
                'message': 'Token refreshed successfully',
                'access': response.data['access']
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'errors': [f"Token refresh failed: {str(e)}"]
            }, status=status.HTTP_400_BAD_REQUEST)



class RegisterView(APIView):
    def post(self, request):
        serializer = CustomUserSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                response = Response({
                    'message': 'User registered successfully',
                    'user': {
                        'username': user.username,
                    }
                }, status=status.HTTP_201_CREATED)
                # Set cookies without Secure and SameSite for development
                response.set_cookie(
                    'access_token',
                    str(refresh.access_token),
                    httponly=True,
                    max_age=3600 , # 1 hour
                    samesite='None'
                )
                response.set_cookie(
                    'refresh_token',
                    str(refresh),
                    httponly=True,
                    max_age=86400,  # 1 day
                    samesite='None'
                )
                return response
            except Exception as e:
                return Response({
                    'errors': [f"Registration failed: {str(e)}"]
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            errors = {}
            for field, error_list in serializer.errors.items():
                if field == 'non_field_errors':
                    errors['general'] = error_list
                else:
                    errors[field] = error_list
            return Response({
                'errors': errors
            }, status=status.HTTP_400_BAD_REQUEST)
        

# Invoke-WebRequest -Uri "http://127.0.0.1:7877/api/v1/register/" -Method POST -Body '{"email":"user3@example.com","password":"securepassword123","confirm_password":"securepassword123","address":"123 Main St","mobile_number":"+1234567890"}' -Headers @{"Content-Type"="application/json";"Origin"="http://localhost:3000"}



class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                user = serializer.validated_data['user']
                refresh = RefreshToken.for_user(user)
                response = Response({
                    'message': 'Login successful',
                    'user': {
                        'username': user.username,
                        'email': user.email,
                        'address': user.address,
                        'mobile_number': user.mobile_number
                    }
                }, status=status.HTTP_200_OK)
                response.set_cookie('access_token', str(refresh.access_token), httponly=True, max_age=3600, samesite='None')
                response.set_cookie('refresh_token', str(refresh), httponly=True, max_age=86400, samesite='None')
                return response
            except Exception as e:
                return Response({
                    'errors': [f"Login failed: {str(e)}"]
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            errors = {}
            for field, error_list in serializer.errors.items():
                if field == 'non_field_errors':
                    errors['general'] = error_list
                else:
                    errors[field] = error_list
            return Response({
                'errors': errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
# Invoke-WebRequest -Uri "http://127.0.0.1:7877/api/v1/login/" -Method POST -Headers @{"Content-Type"="application/json";"Origin"="http://localhost:3000"} -Body '{"login":"user3@example.com","password":"securepassword123"}'
# Invoke-WebRequest -Uri "http://127.0.0.1:7877/api/v1/login/" -Method POST -Headers @{"Content-Type"="application/json";"Origin"="http://localhost:3000"} -Body '{"login":"ugr_2025_3","password":"securepassword123"}'


class ForgetPasswordView(APIView):
    def post(self, request):
        serializer = ForgetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user, otp = serializer.save()
                html_message = render_to_string('emails/otp_email.html', {
                    'username': user.username,
                    'email': user.email,
                    'otp': otp
                })
                plain_message = strip_tags(html_message)
                send_mail(
                    subject='SharFund Password Reset OTP',
                    message=plain_message,
                    from_email='erp@agratasinfotech.com',
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                return Response({
                    'message': 'OTP sent to your email.'
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'errors': [f"Failed to send OTP: {str(e)}"]
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            errors = {}
            for field, error_list in serializer.errors.items():
                errors[field] = error_list
            return Response({
                'errors': errors
            }, status=status.HTTP_400_BAD_REQUEST)

class VerifyOTPView(APIView): 
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            try:
                return Response({
                    'message': 'OTP is Correct'
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'errors': [f"OTP verification failed: {str(e)}"]
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            errors = {}
            for field, error_list in serializer.errors.items():
                errors[field] = error_list
            return Response({
                'errors': errors
            }, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.validated_data['user']
                otp_record = serializer.validated_data['otp_record']
                user.set_password(serializer.validated_data['create_password'])
                user.save()
                otp_record.delete()  # Clear OTP
                return Response({
                    'message': 'Password changed successfully'
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'errors': [f"Password reset failed: {str(e)}"]
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            errors = {}
            for field, error_list in serializer.errors.items():
                errors[field] = error_list
            return Response({
                'errors': errors
            }, status=status.HTTP_400_BAD_REQUEST)
        


class UserProfileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
    


class TeamReferralStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user  # Get the authenticated user

        # Calculate total team (direct + indirect referrals)
        total_team = user.total_team

        # Calculate active team (users with at least 1000 INR in transactions)
        active_team = user.active_team

        # Calculate total referrals (direct referrals only)
        total_referrals = user.total_referrals

        # Calculate active referrals (direct referrals with at least 1000 INR in transactions)
        active_referrals = user.active_referrals

        data = {
            'total_team': total_team,
            'active_team': active_team,
            'total_referrals': total_referrals,
            'active_referrals': active_referrals
        }

        return Response(data, status=status.HTTP_200_OK)



class TransactionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Fetch user's transactions ordered by timestamp
        transactions = Transaction.objects.filter(wallet__user=request.user).order_by('timestamp')
        
        # Prepare serial number mapping (id -> serial number)
        serial_number_map = {txn.id: idx + 1 for idx, txn in enumerate(transactions)}

        # Pass serial number mapping into context
        serializer = TransactionHistorySerializer(
            transactions, many=True, context={'serial_number_map': serial_number_map}
        )
        return Response(serializer.data)


class WithdrawalHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        withdrawals = user.wallet.transactions.filter(transaction_type='WITHDRAWAL').order_by('-timestamp')

        data = []
        for index, transaction in enumerate(withdrawals, start=1):
            serializer = WithdrawalHistorySerializer(transaction, context={'serial_number': index})
            data.append(serializer.data)

        return Response(data)



class CustomerProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = CustomerProfileSerializer(request.user)
        return Response(serializer.data)
    
    # The serializer's update method handles both user and payment details
    def put(self, request):
        user = request.user
        serializer = CustomerProfileSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save() 
            return Response(CustomerProfileSerializer(user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyReferralsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get the logged-in user
        user = request.user

        # Fetch all users referred by the current user
        referrals = CustomUser.objects.filter(referred_by=user).select_related('wallet')

        # Serialize the data
        serializer = ReferralSerializer(referrals, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    


class MonthlyIncomeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        monthly_incomes = MonthlyIncome.objects.filter(user=request.user)
        serializer = MonthlyIncomeSerializer(monthly_incomes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)