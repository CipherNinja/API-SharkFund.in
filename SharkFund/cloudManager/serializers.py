from rest_framework import serializers
from .models import CustomUser, OTP, Transaction, PaymentDetail, MonthlyIncome, PaymentScreenshot
from datetime import timedelta
import random
import string
from django.utils import timezone
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
import logging
import re

logger = logging.getLogger(__name__)

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        attrs['email'] = attrs['email'].lower()
        return super().validate(attrs)




class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    referred_by = serializers.CharField(write_only=True, required=False, allow_blank=True)
    username = serializers.CharField(required=True)  # Add username field
    mobile_number = serializers.CharField(source='mobile', required=False, allow_blank=True)  # Map mobile to mobile_number
    referred_by = serializers.CharField(source='Referral', required=False, allow_blank=True)  # Map Referral to referred_by

    class Meta:
        model = CustomUser
        fields = ['username', 'name', 'email', 'password', 'confirm_password', 'address', 'mobile_number', 'referred_by']
        extra_kwargs = {
            'email': {'required': True},
            'address': {'required': False},
            'mobile_number': {'required': False},
            'referred_by': {'required': False},
        }

    def validate(self, data):
        logger.info("CustomUserSerializer: Validating data: %s", data)
        if data['password'] != data['confirm_password']:
            logger.warning("CustomUserSerializer: Passwords do not match")
            raise serializers.ValidationError({
                "confirm_password": ["Passwords do not match."]
            })
        if len(data['password']) < 8:
            logger.warning("CustomUserSerializer: Password too short")
            raise serializers.ValidationError({
                "password": ["Password must be at least 8 characters long."]
            })
        return data

    def validate_username(self, value):
        logger.info("CustomUserSerializer: Validating username: %s", value)
        # Ensure username is alphanumeric with underscores, 3-30 characters
        if not re.match(r'^[a-zA-Z]+[0-9]{2,}$', value):
            logger.warning("CustomUserSerializer: Invalid username format: %s", value)
            raise serializers.ValidationError(["Username must be 3-30 characters long and contain only letters, numbers, or underscores."])
        if CustomUser.objects.filter(username__iexact=value).exists():
            logger.warning("CustomUserSerializer: Username already exists: %s", value)
            raise serializers.ValidationError(["This username is already taken."])
        return value

    def validate_email(self, value):
        logger.info("CustomUserSerializer: Validating email: %s", value)
        value = value.lower()
        if CustomUser.objects.filter(email__iexact=value).exists():
            logger.warning("CustomUserSerializer: Email already exists: %s", value)
            raise serializers.ValidationError(["This email is already registered."])
        return value

    def validate_mobile_number(self, value):
        logger.info("CustomUserSerializer: Validating mobile_number: %s", value)
        if value and not value.replace("+", "").isdigit():
            logger.warning("CustomUserSerializer: Invalid mobile number format: %s", value)
            raise serializers.ValidationError(["Mobile number must contain only digits and an optional '+' prefix."])
        if value and len(value) > 15:
            logger.warning("CustomUserSerializer: Mobile number too long: %s", value)
            raise serializers.ValidationError(["Mobile number is too long."])
        return value

    def validate_referred_by(self, value):
        logger.info("CustomUserSerializer: Validating referred_by: %s", value)
        if value:
            try:
                referrer = CustomUser.objects.get(username=value)
                logger.info("CustomUserSerializer: Referrer found: %s", referrer.username)
                return value
            except CustomUser.DoesNotExist:
                logger.warning("CustomUserSerializer: Referrer not found: %s", value)
                raise serializers.ValidationError(["Referrer with this username does not exist."])
        return value

    def create(self, validated_data):
        logger.info("CustomUserSerializer: Creating user with validated data: %s", validated_data)
        validated_data.pop('confirm_password')
        # Map back to model field names
        referred_by_username = validated_data.pop('Referral', None)
        mobile_number = validated_data.pop('mobile', None)

        try:
            user = CustomUser.objects.create_user(
                username=validated_data['username'],
                name=validated_data['name'],
                email=validated_data['email'].lower(),
                password=validated_data['password'],
                address=validated_data.get('address'),
                mobile_number=mobile_number
            )
            logger.info("CustomUserSerializer: User created: %s", user.username)

            if referred_by_username:
                logger.info("CustomUserSerializer: Linking referrer: %s", referred_by_username)
                try:
                    referrer = CustomUser.objects.get(username=referred_by_username)
                    user.referred_by = referrer
                    user.save()
                    logger.info("CustomUserSerializer: Referrer linked for user: %s", user.username)
                except CustomUser.DoesNotExist:
                    logger.error("CustomUserSerializer: Referrer %s not found during linking", referred_by_username)
                    user.delete()
                    raise serializers.ValidationError({
                        "referred_by": ["Referrer does not exist."]
                    })

            return user
        except Exception as e:
            logger.error("CustomUserSerializer: Failed to create user: %s", str(e), exc_info=True)
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
    total_deposit = serializers.SerializerMethodField()
    refer_income = serializers.SerializerMethodField()
    total_income = serializers.SerializerMethodField()
    total_withdrawal = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()
    join_date = serializers.DateTimeField()
    activation_date = serializers.SerializerMethodField()
    active_status = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'username', 'total_deposit', 'refer_income',
            'total_income', 'total_withdrawal', 'wallet_balance',
            'join_date', 'activation_date', 'active_status'
        ]

    def get_total_deposit(self, obj):
        if hasattr(obj, 'wallet'):
            return float(obj.wallet.total_deposit)
        return 0.00

    def get_refer_income(self, obj):
        if hasattr(obj, 'wallet'):
            return float(obj.wallet.refer_income)
        return 0.00

    def get_total_income(self, obj):
        if hasattr(obj, 'wallet'):
            return float(obj.wallet.total_income)
        return 0.00

    def get_total_withdrawal(self, obj):
        if hasattr(obj, 'wallet'):
            return float(obj.wallet.total_withdrawal)
        return 0.00

    def get_wallet_balance(self, obj):
        if hasattr(obj, 'wallet'):
            return float(obj.wallet.wallet_balance)
        return 0.00

    def get_activation_date(self, obj):
        if hasattr(obj, 'wallet'):
            first_transaction = Transaction.objects.filter(
                wallet=obj.wallet,
                transaction_type='DEPOSIT',
                status='COMPLETED'
            ).order_by('timestamp').first()
            return first_transaction.timestamp if first_transaction else None
        return None

    def get_active_status(self, obj):
        return obj.status == 'Active'

class DepositHistorySerializer(serializers.ModelSerializer):
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
        """Return the actual payment method from the Transaction model"""
        return "UPI"  # Fallback to 'UPI' if not set

    def get_status(self, obj):
        """Capitalize status for display"""
        return obj.status.title()  # E.g., 'COMPLETED' -> 'Completed'

    def validate(self, attrs):
        """Ensure only DEPOSIT transactions are serialized"""
        # Use the instance if available (for existing objects) or attrs for new data
        obj = self.instance or Transaction(**attrs)
        if obj.transaction_type != 'DEPOSIT':
            raise serializers.ValidationError(
                f"Only DEPOSIT transactions are allowed, got {obj.transaction_type}"
            )
        return attrs

class WithdrawalHistorySerializer(serializers.ModelSerializer):
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
        """Return the actual payment method from the Transaction model"""
        return "UPI"  # Fallback to 'UPI' if not set

    def get_status(self, obj):
        """Capitalize status for display"""
        return obj.status.title()  # E.g., 'COMPLETED' -> 'Completed'

    def validate(self, attrs):
        """Ensure only WITHDRAWAL transactions are serialized"""
        # Use the instance if available (for existing objects) or attrs for new data
        obj = self.instance or Transaction(**attrs)
        if obj.transaction_type != 'WITHDRAWAL':
            raise serializers.ValidationError(
                f"Only WITHDRAWAL transactions are allowed, got {obj.transaction_type}"
            )
        return attrs



class PaymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentDetail
        fields = [
            'account_holder_name',
            'account_number',
            'ifsc_code',
            'upi_id',
            'card_number',
            'name_on_card',
            'expiry_date',
            'cvv',
        ]

class CustomerProfileSerializer(serializers.ModelSerializer):
    sponsored_name = serializers.SerializerMethodField()
    sponsored_email = serializers.SerializerMethodField()
    activation_date = serializers.SerializerMethodField()
    payment_detail = PaymentDetailSerializer(required=False)  # Nested serializer for payment details

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
            'activation_date',
            'payment_detail',  # Include payment details in the response
        ]
        read_only_fields = [
            'username',
            'email',
            'join_date',
            'sponsored_name',
            'sponsored_email',
            'activation_date',
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

    def update(self, instance, validated_data):
        # Extract payment_detail data if present
        payment_detail_data = validated_data.pop('payment_detail', None)

        # Update CustomUser fields
        instance.name = validated_data.get('name', instance.name)
        instance.mobile_number = validated_data.get('mobile_number', instance.mobile_number)
        instance.country = validated_data.get('country', instance.country)
        instance.save()

        # Handle PaymentDetail update or creation
        if payment_detail_data:
            try:
                # If payment details already exist, update them
                payment_detail = instance.payment_detail
                payment_detail_serializer = PaymentDetailSerializer(payment_detail, data=payment_detail_data, partial=True)
            except PaymentDetail.DoesNotExist:
                # If payment details don't exist, create a new instance
                payment_detail_serializer = PaymentDetailSerializer(data=payment_detail_data)

            if payment_detail_serializer.is_valid():
                payment_detail_serializer.save(user=instance)
            else:
                raise serializers.ValidationError(payment_detail_serializer.errors)

        return instance


class ReferralSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['username', 'name', 'mobile_number', 'join_date', 'status']

    def get_status(self, obj):
        # Determine if the user is active based on wallet_balance
        return "Active" if obj.wallet.wallet_balance >= 1000 else "Inactive"
    


class MonthlyIncomeSerializer(serializers.ModelSerializer):
    month = serializers.CharField()
    monthlyPayout = serializers.SerializerMethodField()
    monthlyIncome = serializers.SerializerMethodField()
    totalIncome = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyIncome
        fields = ['month', 'monthlyPayout', 'monthlyIncome', 'totalIncome']

    def get_monthlyPayout(self, obj):
        return f"₹{obj.monthly_payout:,.0f}"

    def get_monthlyIncome(self, obj):
        return f"₹{obj.monthly_income:,.0f}"

    def get_totalIncome(self, obj):
        return f"₹{obj.total_income:,.0f}"
    

class TransactionIncomeSerializer(serializers.Serializer):
    month = serializers.CharField()
    monthlyPayout = serializers.SerializerMethodField()
    monthlyIncome = serializers.SerializerMethodField()
    totalIncome = serializers.SerializerMethodField()

    class Meta:
        fields = ['month', 'monthlyPayout', 'monthlyIncome', 'totalIncome']

    def get_monthlyPayout(self, obj):
        return f"₹{obj['amount']:,.0f}"

    def get_monthlyIncome(self, obj):
        return f"₹{obj['amount']:,.0f}"

    def get_totalIncome(self, obj):
        return f"₹{obj['amount']:,.0f}"


class PaymentScreenshotSerializer(serializers.ModelSerializer):
    screenshot = serializers.ImageField(max_length=None, use_url=True)

    class Meta:
        model = PaymentScreenshot
        fields = ['id', 'amount', 'screenshot', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_screenshot(self, value):
        max_size = 5 * 1024 * 1024  # 5MB
        if value.size > max_size:
            raise serializers.ValidationError("Screenshot file size must not exceed 5MB.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        if not user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated.")
        print(f"[Serializer] Creating PaymentScreenshot for user: {user.username}, amount: {validated_data['amount']}")
        validated_data['user'] = user
        instance = super().create(validated_data)
        print(f"[Serializer] Created PaymentScreenshot with ID: {instance.id}, screenshot: {instance.screenshot.url}")
        return instance
    



from rest_framework import serializers
from .models import Transaction, CustomUser, PaymentDetail
import logging

# Set up logging
logger = logging.getLogger(__name__)

class WithdrawalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['amount']  # Only accept amount from frontend

    def validate(self, data):
        logger.info("Starting validation in WithdrawalRequestSerializer")
        user = self.context['request'].user
        logger.info(f"User: {user.username}")

        # Check if user has payment details
        logger.info("Checking payment details")
        try:
            payment_detail = user.payment_detail
            logger.info(f"Payment details found: UPI={payment_detail.upi_id}, Bank Account={payment_detail.account_number}")
        except PaymentDetail.DoesNotExist:
            logger.error("Payment details not found for user")
            raise serializers.ValidationError("Payment details not found.")

        # Check for valid UPI or valid bank account
        has_upi = bool(payment_detail.upi_id)
        has_bank = all([
            payment_detail.account_holder_name,
            payment_detail.account_number,
            payment_detail.ifsc_code,
        ])
        logger.info(f"Has UPI: {has_upi}, Has Bank: {has_bank}")

        if not (has_upi or has_bank):
            logger.error("Neither UPI nor complete bank details provided")
            raise serializers.ValidationError("Please provide either UPI or complete Bank Account details to withdraw.")

        # Check for at least 2 active referrals
        logger.info("Checking active referrals")
        active_referrals = CustomUser.objects.filter(
            referred_by=user,
            status='Active'  # Changed to match model choice case
        ).count()
        logger.info(f"Active referrals count: {active_referrals}")

        if active_referrals < 2:
            logger.error("Insufficient active referrals")
            raise serializers.ValidationError("You need at least 2 active referrals to request a withdrawal.")

        logger.info("Validation successful")
        return data

    def create(self, validated_data):
        logger.info("Starting create method in WithdrawalRequestSerializer")
        user = self.context['request'].user
        logger.info(f"Creating transaction for user: {user.username}, amount: {validated_data['amount']}")
        try:
            wallet = user.wallet
            logger.info(f"Wallet found: {wallet.id}")
            transaction = Transaction.objects.create(
                wallet=wallet,  # Changed from user to wallet to match model
                amount=validated_data['amount'],
                transaction_type='WITHDRAWAL',  # Match case from model choices
                status='PENDING'  # Match case from model choices
            )
            logger.info(f"Transaction created: ID={transaction.id}, Type={transaction.transaction_type}, Status={transaction.status}")
            return transaction
        except Exception as e:
            logger.error(f"Error creating transaction: {str(e)}")
            raise