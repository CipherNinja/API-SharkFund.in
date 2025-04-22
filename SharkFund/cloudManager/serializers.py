from rest_framework import serializers
from .models import CustomUser, OTP, Transaction
from datetime import timedelta
import random
import string
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
    referred_by = serializers.CharField(write_only=True, required=False, allow_blank=True)  # New field for referrer username

    class Meta:
        model = CustomUser
        fields = ['name', 'email', 'password', 'confirm_password', 'address', 'mobile_number', 'referred_by']
        extra_kwargs = {
            'email': {'required': True},
            'address': {'required': False},
            'mobile_number': {'required': False},
            'referred_by': {'required': False},
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

    def validate_referred_by(self, value):
        # Validate referrer username if provided
        if value:
            try:
                referrer = CustomUser.objects.get(username=value)
                return value
            except CustomUser.DoesNotExist:
                raise serializers.ValidationError(["Referrer with this username does not exist."])
        return value

    def create(self, validated_data):
        # Remove confirm_password and referred_by as they are not model fields
        validated_data.pop('confirm_password')
        referred_by_username = validated_data.pop('referred_by', None)

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
                name=validated_data['name'],
                username=username,
                email=validated_data['email'].lower(),
                password=validated_data['password'],
                address=validated_data.get('address'),
                mobile_number=validated_data.get('mobile_number')
            )

            # Link referrer if referred_by_username is provided
            if referred_by_username:
                referrer = CustomUser.objects.get(username=referred_by_username)
                user.referred_by = referrer
                user.save()

            return user
        except Exception as e:
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
    


class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        value = value.lower()
        if not CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(["Email ID doesn't exist."])
        return value

    def save(self):
        email = self.validated_data['email']
        user = CustomUser.objects.get(email=email)

        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))

        # Store OTP
        OTP.objects.filter(user=user).delete()  # Clear old OTPs
        OTP.objects.create(
            user=user,
            otp=otp,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        return user, otp

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, required=True)

    def validate(self, data):
        email = data.get('email').lower()
        otp = data.get('otp')

        try:
            user = CustomUser.objects.get(email=email)
            otp_record = OTP.objects.filter(user=user, otp=otp).first()
            if not otp_record:
                raise serializers.ValidationError({
                    "otp": ["Invalid OTP."]
                })
            if not otp_record.is_valid():
                otp_record.delete()
                raise serializers.ValidationError({
                    "otp": ["OTP has expired."]
                })
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError({
                "email": ["Email ID doesn't exist."]
            })

        return data

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    create_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate(self, data):
        email = data.get('email').lower()
        create_password = data.get('create_password')
        confirm_password = data.get('confirm_password')

        # Validate email existence
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError({
                "email": ["Email ID doesn't exist."]
            })

        # Check for valid OTP
        otp_record = OTP.objects.filter(user=user).first()
        if not otp_record:
            raise serializers.ValidationError({
                "general": ["No valid OTP found. Please request a new OTP."]
            })
        if not otp_record.is_valid():
            otp_record.delete()
            raise serializers.ValidationError({
                "general": ["OTP has expired. Please request a new OTP."]
            })

        # Validate passwords
        if create_password != confirm_password:
            raise serializers.ValidationError({
                "confirm_password": ["Passwords do not match."]
            })
        if len(create_password) < 8:
            raise serializers.ValidationError({
                "create_password": ["Password must be at least 8 characters long."]
            })

        data['user'] = user
        data['otp_record'] = otp_record  # Pass OTP record to view
        return data
    



class UserProfileSerializer(serializers.ModelSerializer):
    total_income = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()
    total_withdrawal = serializers.SerializerMethodField()
    join_date = serializers.DateTimeField()

    activation_date = serializers.SerializerMethodField()
    active_status = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'username', 'total_income', 'wallet_balance', 'total_withdrawal',
            'join_date', 'activation_date', 'active_status'
        ]

    def get_total_income(self, obj):
        if hasattr(obj, 'wallet'):
            return obj.wallet.total_income
        return 0.00

    def get_wallet_balance(self, obj):
        if hasattr(obj, 'wallet'):
            return obj.wallet.wallet_balance
        return 0.00

    def get_total_withdrawal(self, obj):
        if hasattr(obj, 'wallet'):
            return obj.wallet.total_withdrawal
        return 0.00

    def get_activation_date(self, obj):
        if hasattr(obj, 'wallet'):
            first_transaction = Transaction.objects.filter(wallet=obj.wallet).order_by('timestamp').first()
            if first_transaction:
                return first_transaction.timestamp
            else:
                return "Inactive due to Insufficient Balance in wallet"
        return "Wallet not created"

    def get_active_status(self, obj):
        if hasattr(obj, 'wallet'):
            return Transaction.objects.filter(wallet=obj.wallet, amount__gte=1000).exists()
        return False


from rest_framework import serializers
from .models import Transaction

class TransactionHistorySerializer(serializers.ModelSerializer):
    serial_number = serializers.SerializerMethodField()
    method = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = ['serial_number', 'amount', 'timestamp', 'method', 'status']

    def get_serial_number(self, obj):
        """Serial number based on queryset ordering"""
        return self.context['serial_number_map'][obj.id]

    def get_method(self, obj):
        return "PayPal"

    def get_status(self, obj):
        return "Completed"


class WithdrawalHistorySerializer(serializers.ModelSerializer):
    serial_number = serializers.SerializerMethodField()
    method = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = ['serial_number', 'amount', 'timestamp', 'method', 'status']

    def get_serial_number(self, obj):
        # Serial number based on the queryset order in the view
        return self.context['serial_number']

    def get_method(self, obj):
        return 'PayPal'

    def get_status(self, obj):
        return 'Completed'



class CustomerProfileSerializer(serializers.ModelSerializer):
    sponsored_name = serializers.SerializerMethodField()
    sponsored_email = serializers.SerializerMethodField()
    activation_date = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'username',
            'email',
            'name',
            'mobile_number',
            'country',
            'join_date',
            'sponsored_name',
            'sponsored_email',
            'activation_date'
        ]
        read_only_fields = [
            'username',
            'email',
            'join_date',
            'sponsored_name',
            'sponsored_email',
            'activation_date'
        ]

    def get_sponsored_name(self, obj):
        if obj.referred_by:
            return obj.referred_by.name or "NA"
        return "NA"

    def get_sponsored_email(self, obj):
        if obj.referred_by:
            return obj.referred_by.email or "NA"
        return "NA"

    def get_activation_date(self, obj):
        first_transaction = Transaction.objects.filter(wallet__user=obj).order_by('timestamp').first()
        if first_transaction:
            return first_transaction.timestamp
        return "NA"
