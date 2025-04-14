from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CustomUserSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

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
                        'email': user.email,
                        'address': user.address,
                        'mobile_number': user.mobile_number
                    }
                }, status=status.HTTP_201_CREATED)
                # Set cookies without Secure and SameSite for development
                response.set_cookie(
                    'access_token',
                    str(refresh.access_token),
                    httponly=True,
                    max_age=3600  # 1 hour
                )
                response.set_cookie(
                    'refresh_token',
                    str(refresh),
                    httponly=True,
                    max_age=86400  # 1 day
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
