from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone
from django.core.validators import MinValueValidator, RegexValidator
from django.db.models.signals import pre_save, pre_delete, post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db.models import Sum
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Choices for account activation status
ACCOUNT_STATUS_CHOICES = (
    ('Active', 'Active'),
    ('InActive', 'InActive'),
)

PAYMENT_STATUS_CHOICES = (
    ('Confirmed', 'Confirmed'),
    ('Pending', 'Pending'),
    ('Failed', 'Failed'),
)

class CustomUser(AbstractUser):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    address = models.TextField(null=True, blank=True)
    mobile_number = models.CharField(max_length=15, null=True, blank=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    join_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=10,
        choices=ACCOUNT_STATUS_CHOICES,
        default='InActive',
        verbose_name="Account Status"
    )
    last_active = models.DateTimeField(null=True, blank=True, verbose_name="Activation Date")
    country = models.CharField(default="India", max_length=100)

    def __str__(self):
        return self.username

    def update_last_active(self):
        self.last_active = timezone.now()
        self.save()

    @property
    def total_team(self):
        def count_referrals(user):
            referrals = user.referrals.all()
            direct_count = referrals.count()
            indirect_count = sum(count_referrals(referral) for referral in referrals)
            return direct_count + indirect_count
        return count_referrals(self)

    @property
    def active_team(self):
        active_users = set()
        def collect_active_referrals(user):
            if not hasattr(user, 'wallet'):
                return
            if user.status == 'Active':
                active_users.add(user.id)
            for referral in user.referrals.all():
                collect_active_referrals(referral)
        user_with_data = CustomUser.objects.prefetch_related(
            models.Prefetch('referrals', queryset=CustomUser.objects.prefetch_related('wallet', 'referrals')),
            'wallet'
        ).get(id=self.id)
        collect_active_referrals(user_with_data)
        return len(active_users)

    @property
    def active_referrals(self):
        return self.referrals.filter(status='Active').distinct().count()

    @property
    def total_referrals(self):
        return self.referrals.count()

class OTP(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        return timezone.now() <= self.expires_at

    def __str__(self):
        return f"OTP {self.otp} for {self.user.email}"

class Wallet(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='wallet')
    total_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    refer_income = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    total_income = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    total_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Wallet for {self.user.username}"

    def calculate_balance(self):
        """
        Calculate withdrawable balance (INCOME + REFERRAL minus WITHDRAWAL transactions).
        """
        income = self.transactions.filter(transaction_type='INCOME', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0
        referral = self.transactions.filter(transaction_type='REFERRAL', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0
        withdrawals = self.transactions.filter(transaction_type='WITHDRAWAL', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0
        return income + referral - withdrawals

    def update_from_transactions(self):
        """
        Update wallet fields based on transactions.
        """
        deposits = self.transactions.filter(transaction_type__in=['DEPOSIT', 'RESET_DEPOSIT'], status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0
        withdrawals = self.transactions.filter(transaction_type='WITHDRAWAL', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0
        incomes = self.transactions.filter(transaction_type='INCOME', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0
        referrals = self.transactions.filter(transaction_type='REFERRAL', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0

        logger.info(f"Updating wallet for {self.user.username}: deposits={deposits}, incomes={incomes}, referrals={referrals}, withdrawals={withdrawals}")

        self.total_deposit = max(deposits, 0)
        self.total_income = incomes
        self.refer_income = referrals
        self.total_withdrawal = withdrawals
        self.wallet_balance = incomes + referrals - withdrawals
        self.save()

    @transaction.atomic
    def add_funds(self, amount):
        """
        Add funds to total_deposit (non-withdrawable).
        """
        if amount <= 0:
            return False, "Amount must be positive."
        try:
            transaction = Transaction.objects.create(
                wallet=self,
                amount=amount,
                transaction_type='DEPOSIT',
                status='COMPLETED',
                description=f"Deposit of {amount}"
            )
            logger.info(f"Created DEPOSIT transaction {transaction.id} for {self.user.username} with amount {amount}")
            self.update_from_transactions()
            logger.info(f"Updated total_deposit for {self.user.username} to {self.total_deposit}")
            return True, "Deposit successful."
        except Exception as e:
            logger.error(f"Failed to add funds for {self.user.username}: {str(e)}")
            return False, f"Deposit failed: {str(e)}"

    @transaction.atomic
    def withdraw_funds(self, amount):
        """
        Withdraw funds from wallet_balance only.
        """
        if amount <= 0:
            return False, "Amount must be positive."
        self.refresh_from_db()
        current_balance = self.calculate_balance()
        if current_balance < amount:
            return False, f"Insufficient withdrawable balance: Current balance is {current_balance}, but withdrawal amount is {amount}."
        try:
            transaction = Transaction.objects.create(
                wallet=self,
                amount=amount,
                transaction_type='WITHDRAWAL',
                status='COMPLETED',
                description=f"Withdrawal of {amount}"
            )
            logger.info(f"Created WITHDRAWAL transaction {transaction.id} for {self.user.username} with amount {amount}")
            self.update_from_transactions()
            return True, "Withdrawal successful."
        except Exception as e:
            logger.error(f"Failed to withdraw funds for {self.user.username}: {str(e)}")
            return False, f"Withdrawal failed: {str(e)}"

class Transaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    transaction_type = models.CharField(
        max_length=15,
        choices=[
            ('DEPOSIT', 'Deposit'),
            ('WITHDRAWAL', 'Withdrawal'),
            ('INCOME', 'Income'),
            ('RESET_DEPOSIT', 'Reset Deposit'),
            ('REFERRAL', 'Referral'),
        ]
    )
    status = models.CharField(
        max_length=10,
        choices=[('COMPLETED', 'Completed'), ('PENDING', 'Pending'), ('FAILED', 'Failed')],
        default='PENDING'
    )
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.transaction_type} of ${self.amount} for {self.wallet.user.username}"

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        wallet = Wallet.objects.select_for_update().get(pk=self.wallet.pk)
        previous = None
        if not is_new:
            previous = Transaction.objects.get(pk=self.pk)

        if is_new and self.transaction_type == 'WITHDRAWAL' and self.status == 'COMPLETED':
            if wallet.calculate_balance() < self.amount:
                logger.error(f"Insufficient balance for WITHDRAWAL transaction for {wallet.user.username}: balance={wallet.calculate_balance()}, amount={self.amount}")
                raise ValidationError(f"Insufficient withdrawable balance: {wallet.calculate_balance()} available, {self.amount} requested.")

        super().save(*args, **kwargs)

        if self.status == 'COMPLETED':
            wallet.update_from_transactions()
            logger.info(f"Transaction {self.id} ({self.transaction_type}) for {wallet.user.username} triggered wallet update")

class PaymentDetail(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='payment_detail')
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=20, blank=True, null=True, validators=[
        RegexValidator(r'^\d+$', 'Account number must contain only digits.')
    ])
    ifsc_code = models.CharField(max_length=11, blank=True, null=True, validators=[
        RegexValidator(r'^.{11}$', 'IFSC code must be exactly 11 characters.')
    ])
    upi_id = models.CharField(max_length=100, blank=True, null=True, validators=[
        RegexValidator(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9]+$', 'Invalid UPI ID format.')
    ])
    card_number = models.CharField(max_length=19, blank=True, null=True, validators=[
        RegexValidator(r'^\d{16}$', 'Card number must be exactly 16 digits.')
    ])
    name_on_card = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.CharField(max_length=5, blank=True, null=True, validators=[
        RegexValidator(r'^(0[1-9]|1[0-2])\/\d{2}$', 'Expiry date must be in MM/YY format.')
    ])
    cvv = models.CharField(max_length=4, blank=True, null=True, validators=[
        RegexValidator(r'^\d{3,4}$', 'CVV must be 3 or 4 digits.')
    ])

    def __str__(self):
        return f"Payment Details for {self.user.username}"

    def clean(self):
        if not (self.account_number or self.upi_id or self.card_number):
            raise ValidationError("At least one payment method (Bank Account, UPI, or Card) must be provided.")
        if any([self.account_holder_name, self.account_number, self.ifsc_code]):
            if not (self.account_holder_name and self.account_number and self.ifsc_code):
                raise ValidationError("All bank details must be provided if any bank detail is filled.")
        if any([self.card_number, self.name_on_card, self.expiry_date, self.cvv]):
            if not (self.card_number and self.name_on_card and self.expiry_date and self.cvv):
                raise ValidationError("All card details must be provided if any card detail is filled.")

class MonthlyIncome(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='monthly_incomes')
    month = models.CharField(max_length=20)
    monthly_payout = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    monthly_income = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_income = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'month')
        ordering = ['-month']

    def __str__(self):
        return f"{self.month} Income for {self.user.username}"

class PaymentScreenshot(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='payment_screenshots')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    status = models.CharField(choices=PAYMENT_STATUS_CHOICES, max_length=20, default="Pending", verbose_name="Payment Status")
    screenshot = models.ImageField(upload_to='payment_screenshots/%Y/%m/%d/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment of {self.amount} by {self.user.username} on {self.created_at}"

# Signals
@receiver(post_save, sender=CustomUser)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.create(
            user=instance,
            total_deposit=0.00,
            refer_income=0.00,
            total_income=0.00,
            total_withdrawal=0.00,
            wallet_balance=0.00,
            created_at=timezone.now()
        )

@receiver(pre_save, sender=CustomUser)
def handle_referral_income_on_activation(sender, instance, **kwargs):
    if instance.pk:  # Only for existing users being updated
        try:
            old_instance = CustomUser.objects.get(pk=instance.pk)
            if old_instance.status != 'Active' and instance.status == 'Active' and instance.referred_by:
                referrer = instance.referred_by
                if hasattr(referrer, 'wallet'):
                    with transaction.atomic():
                        Transaction.objects.create(
                            wallet=referrer.wallet,
                            amount=Decimal('400.00'),
                            transaction_type='REFERRAL',
                            status='COMPLETED',
                            description=f"Referral bonus for {instance.username}'s activation"
                        )
                        logger.info(f"Credited ₹400 referral income to {referrer.username} for {instance.username}'s activation")
                else:
                    logger.warning(f"Referrer {referrer.username} has no wallet for referral income")
        except CustomUser.DoesNotExist:
            logger.error(f"User {instance.username} not found during pre_save")
            pass

@receiver(post_save, sender=MonthlyIncome)
def update_wallet_on_monthly_income_save(sender, instance, created, **kwargs):
    if created:
        wallet = Wallet.objects.select_for_update().get(user=instance.user)
        with transaction.atomic():
            # Add INCOME transaction
            Transaction.objects.create(
                wallet=wallet,
                amount=instance.total_income,
                transaction_type='INCOME',
                status='COMPLETED',
                description=f"Monthly income for {instance.month}"
            )
            # Reset total_deposit with RESET_DEPOSIT transaction
            current_deposit = wallet.transactions.filter(
                transaction_type__in=['DEPOSIT', 'RESET_DEPOSIT'],
                status='COMPLETED'
            ).aggregate(total=Sum('amount'))['total'] or 0
            if current_deposit > 0:
                Transaction.objects.create(
                    wallet=wallet,
                    amount=-current_deposit,
                    transaction_type='RESET_DEPOSIT',
                    status='COMPLETED',
                    description=f"Reset deposit for {instance.month}"
                )
            logger.info(f"Added MonthlyIncome for {instance.user.username}, created INCOME and RESET_DEPOSIT transactions")

@receiver(pre_delete, sender=MonthlyIncome)
def update_wallet_on_monthly_income_delete(sender, instance, **kwargs):
    wallet = Wallet.objects.select_for_update().get(user=instance.user)
    with transaction.atomic():
        # Find corresponding INCOME transaction
        income_tx = wallet.transactions.filter(
            transaction_type='INCOME',
            status='COMPLETED',
            description=f"Monthly income for {instance.month}"
        ).first()
        if income_tx:
            if wallet.calculate_balance() >= income_tx.amount:
                income_tx.status = 'FAILED'  # Mark as failed instead of deleting
                income_tx.save()
                logger.info(f"Marked INCOME transaction for {instance.user.username} as FAILED for month {instance.month}")
            else:
                logger.error(f"Cannot delete MonthlyIncome for {instance.user.username}: Insufficient balance")
                raise ValidationError(
                    f"Cannot delete monthly income: Insufficient wallet balance ({wallet.calculate_balance()}) "
                    f"to debit {instance.total_income}."
                )