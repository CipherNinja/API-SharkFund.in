from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone
from django.core.validators import MinValueValidator, RegexValidator
from django.db.models.signals import pre_save, pre_delete, post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from decimal import Decimal

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
            referrals = user.referrals.all()  # Count all referrals, regardless of status
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
            if user.status == 'Active':  # Check status and balance
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
    total_income = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    total_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)], editable=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Wallet for {self.user.username}"

    def calculate_balance(self):
        deposits = self.transactions.filter(transaction_type='DEPOSIT', status='SUCCESS').aggregate(total=models.Sum('amount'))['total'] or 0
        withdrawals = self.transactions.filter(transaction_type='WITHDRAWAL', status='SUCCESS').aggregate(total=models.Sum('amount'))['total'] or 0
        add_income = self.transactions.filter(transaction_type='ADD_INCOME', status='SUCCESS').aggregate(total=models.Sum('amount'))['total'] or 0
        return deposits + add_income - withdrawals

    def update_from_transactions(self):
        deposits = self.transactions.filter(transaction_type='DEPOSIT').aggregate(total=models.Sum('amount'))['total'] or 0
        withdrawals = self.transactions.filter(transaction_type='WITHDRAWAL').aggregate(total=models.Sum('amount'))['total'] or 0
        add_income = self.transactions.filter(transaction_type='ADD_INCOME').aggregate(total=models.Sum('amount'))['total'] or 0
        self.total_withdrawal = withdrawals
        self.wallet_balance = deposits + add_income - withdrawals
        self.save()

    @transaction.atomic
    def add_funds(self, amount):
        if amount <= 0:
            return False, "Amount must be positive."
        Transaction.objects.create(wallet=self, amount=amount, transaction_type='DEPOSIT')
        self.update_from_transactions()
        return True, "Deposit successful."

    @transaction.atomic
    def withdraw_funds(self, amount):
        if amount <= 0:
            return False, "Amount must be positive."
        self.refresh_from_db()
        current_balance = self.calculate_balance()
        if current_balance < amount:
            return False, f"Insufficient funds: Current balance is {current_balance}, but withdrawal amount is {amount}."
        Transaction.objects.create(wallet=self, amount=amount, transaction_type='WITHDRAWAL')
        self.update_from_transactions()
        return True, "Withdrawal successful."

    @transaction.atomic
    def add_income(self, amount):
        if amount <= 0:
            return False, "Amount must be positive."
        Transaction.objects.create(wallet=self, amount=amount, transaction_type='ADD_INCOME')
        self.total_income += amount
        self.update_from_transactions()
        return True, "Income added successfully."

class Transaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    transaction_type = models.CharField(max_length=10, choices=[('DEPOSIT', 'Deposit'), ('WITHDRAWAL', 'Withdrawal')])
    status = models.CharField(max_length=10, choices=[('COMPLETED', 'Completed'), ('PENDING', 'Pending'), ('FAILED', 'Failed')])
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.transaction_type} of ${self.amount} for {self.wallet.user.username}"

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self._state.adding  # True if this is a new transaction
        wallet = Wallet.objects.select_for_update().get(pk=self.wallet.pk)

        # Fetch previous transaction if it exists
        previous = None
        if not is_new:
            previous = Transaction.objects.get(pk=self.pk)

        # Perform default save
        super().save(*args, **kwargs)

        # Apply changes only if status is 'COMPLETED'
        if self.status == 'COMPLETED':
            # If new transaction
            if is_new:
                self._apply_wallet_changes(wallet, Decimal('0.00'))
            # If updated transaction
            elif previous:
                self._apply_wallet_changes(wallet, previous.amount, previous.transaction_type, previous.status)

            wallet.save()

    def _apply_wallet_changes(self, wallet, old_amount, old_type=None, old_status=None):
        """
        Adjust wallet based on the transaction type and previous state (for updates).
        """
        # Undo old effect if necessary
        if old_status == 'COMPLETED':
            if old_type == 'DEPOSIT':
                wallet.total_withdrawal -= old_amount
            elif old_type == 'WITHDRAWAL':
                wallet.wallet_balance += old_amount
            elif old_type == 'ADD_INCOME':
                wallet.total_income -= old_amount

        # Apply new effect
        if self.transaction_type == 'DEPOSIT':
            wallet.wallet_balance += self.amount
        elif self.transaction_type == 'WITHDRAWAL':
            if wallet.wallet_balance < self.amount:
                raise ValidationError(f"Insufficient funds: balance={wallet.wallet_balance}, withdrawal={self.amount}")
            wallet.wallet_balance -= self.amount
            wallet.total_withdrawal += self.amount
        elif self.transaction_type == 'ADD_INCOME':
            wallet.total_income += self.amount
            wallet.wallet_balance += self.amount

class PaymentDetail(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='payment_detail')
    
    # Bank Account Details
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=20, blank=True, null=True, validators=[
        RegexValidator(r'^\d+$', 'Account number must contain only digits.')
    ])
    ifsc_code = models.CharField(max_length=11, blank=True, null=True, validators=[
        RegexValidator(r'^[A-Z]{4}0[A-Z0-9]{6}$', 'Invalid IFSC code format.')
    ])

    # UPI Details
    upi_id = models.CharField(max_length=100, blank=True, null=True, validators=[
        RegexValidator(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', 'Invalid UPI ID format.')
    ])

    # Card Details
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
        # Ensure at least one payment method is provided
        if not (self.account_number or self.upi_id or self.card_number):
            raise ValidationError("At least one payment method (Bank Account, UPI, or Card) must be provided.")

        # If bank details are provided, all bank fields should be filled
        if any([self.account_holder_name, self.account_number, self.ifsc_code]):
            if not (self.account_holder_name and self.account_number and self.ifsc_code):
                raise ValidationError("All bank details (Account Holder Name, Account Number, IFSC Code) must be provided if any bank detail is filled.")

        # If card details are provided, all card fields should be filled
        if any([self.card_number, self.name_on_card, self.expiry_date, self.cvv]):
            if not (self.card_number and self.name_on_card and self.expiry_date and self.cvv):
                raise ValidationError("All card details (Card Number, Name on Card, Expiry Date, CVV) must be provided if any card detail is filled.")

class MonthlyIncome(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='monthly_incomes')
    month = models.CharField(max_length=20)  # e.g., "January 2025"
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

# Signals for Transaction
@receiver(pre_save, sender=Transaction)
def update_wallet_on_transaction_save(sender, instance, **kwargs):
    if instance.pk:
        old_transaction = Transaction.objects.get(pk=instance.pk)
        if old_transaction.amount != instance.amount or old_transaction.transaction_type != instance.transaction_type:
            instance.wallet.update_from_transactions()
            if old_transaction.transaction_type == 'ADD_INCOME' and instance.transaction_type != 'ADD_INCOME':
                instance.wallet.total_income -= old_transaction.amount
            elif instance.transaction_type == 'ADD_INCOME' and old_transaction.transaction_type != 'ADD_INCOME':
                instance.wallet.total_income += instance.amount
            instance.wallet.save()

@receiver(pre_delete, sender=Transaction)
def prevent_transaction_delete(sender, instance, **kwargs):
    print(f"Attempted deletion of transaction {instance.id} for wallet {instance.wallet.user.username} at {timezone.now()}")

@receiver(post_save, sender=CustomUser)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.create(
            user=instance,
            total_income=0.00,
            total_withdrawal=0.00,
            wallet_balance=0.00,
            created_at=timezone.now()
        )

# Signals for MonthlyIncome
@receiver(post_save, sender=MonthlyIncome)
def update_wallet_on_monthly_income_save(sender, instance, created, **kwargs):
    if created:
        wallet = Wallet.objects.select_for_update().get(user=instance.user)
        with transaction.atomic():
            # Credit total_income and wallet_balance
            wallet.total_income += instance.total_income
            wallet.wallet_balance += instance.total_income
            wallet.save()

@receiver(pre_delete, sender=MonthlyIncome)
def update_wallet_on_monthly_income_delete(sender, instance, **kwargs):
    wallet = Wallet.objects.select_for_update().get(user=instance.user)
    with transaction.atomic():
        # Debit total_income and wallet_balance
        if wallet.wallet_balance >= instance.total_income:
            wallet.total_income -= instance.total_income
            wallet.wallet_balance -= instance.total_income
            wallet.save()
        else:
            raise ValidationError(
                f"Cannot delete monthly income: Insufficient wallet balance ({wallet.wallet_balance}) "
                f"to debit {instance.total_income}."
            )