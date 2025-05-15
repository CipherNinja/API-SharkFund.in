from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone
from django.core.validators import MinValueValidator, RegexValidator
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError

class CustomUser(AbstractUser):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    address = models.TextField(null=True, blank=True)
    mobile_number = models.CharField(max_length=15, null=True, blank=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    join_date = models.DateTimeField(default=timezone.now)
    last_active = models.DateTimeField(null=True, blank=True)
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
            if user.wallet.wallet_balance >= 1000:
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
    def total_referrals(self):
        return self.referrals.count()

    @property
    def active_referrals(self):
        return self.referrals.filter(wallet__wallet_balance__gte=1000).distinct().count()

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
        deposits = self.transactions.filter(transaction_type='DEPOSIT').aggregate(total=models.Sum('amount'))['total'] or 0
        withdrawals = self.transactions.filter(transaction_type='WITHDRAWAL').aggregate(total=models.Sum('amount'))['total'] or 0
        add_income = self.transactions.filter(transaction_type='ADD_INCOME').aggregate(total=models.Sum('amount'))['total'] or 0
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
    transaction_type = models.CharField(max_length=10, choices=[('DEPOSIT', 'Deposit'), ('WITHDRAWAL', 'Withdrawal'), ('ADD_INCOME', 'Add Income')])
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.transaction_type} of ${self.amount} for {self.wallet.user.username}"

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = not self.pk
        if is_new and self.transaction_type == 'WITHDRAWAL':
            wallet = Wallet.objects.select_for_update().get(id=self.wallet.id)
            current_balance = wallet.calculate_balance()
            if current_balance < self.amount:
                raise ValidationError(
                    f"Insufficient funds: Current balance is {current_balance}, but withdrawal amount is {self.amount}."
                )
        super().save(*args, **kwargs)
        if is_new and self.transaction_type == 'ADD_INCOME':
            self.wallet.total_income += self.amount
            self.wallet.save()
        self.wallet.update_from_transactions()

    def delete(self, *args, **kwargs):
        print(f"Attempted deletion of transaction {self.id} for wallet {self.wallet.user.username} at {timezone.now()}")
        return None

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
        unique_together = ('user', 'month')  # Prevent duplicate entries for the same user and month
        ordering = ['-month']  # Order by month descending (most recent first)

    def __str__(self):
        return f"{self.month} Income for {self.user.username}"

# Signals for Transaction (unchanged)
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