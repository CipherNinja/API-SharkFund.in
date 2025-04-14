from rest_framework import serializers
from .models import CustomUser
from django.utils import timezone
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        attrs['email'] = attrs['email'].lower()
        return super().validate(attrs)





class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'confirm_password', 'address', 'mobile_number']
        extra_kwargs = {
            'email': {'required': True},
            'address': {'required': False},
            'mobile_number': {'required': False},
        }

    def validate(self, data):
        # Check if password and confirm_password match
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({
                "confirm_password": ["Passwords do not match."]
            })

        # Basic password validation (e.g., minimum length)
        if len(data['password']) < 8:
            raise serializers.ValidationError({
                "password": ["Password must be at least 8 characters long."]
            })

        return data

    def validate_email(self, value):
        # Normalize email to lowercase to avoid case-sensitive duplicates
        value = value.lower()
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(["This email is already registered."])
        return value

    def validate_mobile_number(self, value):
        # Optional: Add basic mobile number validation
        if value and not value.replace("+", "").isdigit():
            raise serializers.ValidationError(["Mobile number must contain only digits and an optional '+' prefix."])
        if value and len(value) > 15:
            raise serializers.ValidationError(["Mobile number is too long."])
        return value

    def create(self, validated_data):
        # Remove confirm_password as it's not needed for user creation
        validated_data.pop('confirm_password')

        # Generate username: ugr_YEAR_NUMBER
        current_year = timezone.now().year
        latest_user = CustomUser.objects.filter(
            username__startswith=f'ugr_{current_year}_'
        ).order_by('-username').first()

        if latest_user:
            try:
                latest_number = int(latest_user.username.split('_')[-1])
                new_number = latest_number + 1
            except ValueError:
                new_number = 1
        else:
            new_number = 1

        username = f'ugr_{current_year}_{new_number}'

        try:
            # Create the user
            user = CustomUser.objects.create_user(
                username=username,
                email=validated_data['email'].lower(),  # Store email in lowercase
                password=validated_data['password'],
                address=validated_data.get('address'),
                mobile_number=validated_data.get('mobile_number')
            )
            return user
        except Exception as e:
            # Catch any unexpected errors during user creation
            raise serializers.ValidationError({
                "non_field_errors": [f"Failed to create user: {str(e)}"]
            })
    

class LoginSerializer(serializers.Serializer):
    login = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate(self, data):
        login = data.get('login').lower()
        password = data.get('password')

        user = authenticate(request=self.context.get('request'), username=login, password=password)
        if not user:
            raise serializers.ValidationError({
                "non_field_errors": ["Invalid email/username or password."]
            })

        data['user'] = user
        return data