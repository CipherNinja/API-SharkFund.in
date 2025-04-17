from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver

class CustomUser(AbstractUser):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)  # Ensures email is unique
    address = models.TextField(null=True, blank=True)
    mobile_number = models.CharField(max_length=15, null=True, blank=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')  # Tracks who referred this user
    join_date = models.DateTimeField(default=timezone.now)  # When user joined
    last_active = models.DateTimeField(null=True, blank=True)  # Last activity timestamp (optional)

    def __str__(self):
        return self.username

    def update_last_active(self):
        """Update the last active timestamp (optional, can be removed if unused)."""
        self.last_active = timezone.now()
        self.save()

    @property
    def total_team(self):
        """Calculate total team (direct + indirect referrals)."""
        return self.referrals.count() + sum(user.total_team for user in self.referrals.all())

    @property
    def active_team(self):
        """Calculate active team (users with total transactions >= INR 1000)."""
        active_users = set()
        def collect_active_referrals(user):
            for referral in user.referrals.all():
                if referral.wallet.transactions.filter(amount__gte=1000).exists():
                    active_users.add(referral)
                collect_active_referrals(referral)
        collect_active_referrals(self)
        if self.wallet.transactions.filter(amount__gte=1000).exists():
            active_users.add(self)
        return len(active_users)

    @property
    def total_referrals(self):
        """Count direct referrals."""
        return self.referrals.count()

    @property
    def active_referrals(self):
        """Count active direct referrals (with total transactions >= INR 1000)."""
        return self.referrals.filter(
            wallet__transactions__amount__gte=1000
        ).distinct().count()


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

    def update_from_transactions(self):
        """Recalculate wallet state based on transaction history."""
        deposits = self.transactions.filter(transaction_type='DEPOSIT').aggregate(total=models.Sum('amount'))['total'] or 0
        withdrawals = self.transactions.filter(transaction_type='WITHDRAWAL').aggregate(total=models.Sum('amount'))['total'] or 0
        add_income = self.transactions.filter(transaction_type='ADD_INCOME').aggregate(total=models.Sum('amount'))['total'] or 0
        # Set total_withdrawal to the sum of all WITHDRAWAL transactions
        self.total_withdrawal = withdrawals
        # wallet_balance is net of deposits, add_income (credits), and withdrawals (debits)
        self.wallet_balance = deposits + add_income - withdrawals
        self.save()

    def add_funds(self, amount):
        """Add funds and create a transaction record."""
        if amount <= 0:
            return False
        Transaction.objects.create(wallet=self, amount=amount, transaction_type='DEPOSIT')
        self.update_from_transactions()
        return True

    def withdraw_funds(self, amount):
        """Withdraw funds and create a transaction record if sufficient balance."""
        if amount <= 0 or self.wallet_balance < amount:
            return False
        Transaction.objects.create(wallet=self, amount=amount, transaction_type='WITHDRAWAL')
        self.update_from_transactions()
        return True

    def add_income(self, amount):
        """Add income and create a transaction record."""
        if amount <= 0:
            return False
        Transaction.objects.create(wallet=self, amount=amount, transaction_type='ADD_INCOME')
        self.total_income += amount  # Increment total_income for ADD_INCOME
        self.update_from_transactions()
        return True


class Transaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=[('DEPOSIT', 'Deposit'), ('WITHDRAWAL', 'Withdrawal'), ('ADD_INCOME', 'Add Income')])
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.transaction_type} of ${self.amount} for {self.wallet.user.username}"

    def save(self, *args, **kwargs):
        """Override save to update wallet state after transaction change."""
        is_new = not self.pk  # Check if this is a new transaction
        super().save(*args, **kwargs)
        if is_new and self.transaction_type == 'ADD_INCOME':
            self.wallet.total_income += self.amount  # Increment total_income for new ADD_INCOME
            self.wallet.save()
        self.wallet.update_from_transactions()

    def delete(self, *args, **kwargs):
        """Prevent deletion and log to console."""
        print(f"Attempted deletion of transaction {self.id} for wallet {self.wallet.user.username} at {timezone.now()}")
        return None  # Pass without raising an error


# Signal to update wallet on transaction changes
@receiver(pre_save, sender=Transaction)
def update_wallet_on_transaction_save(sender, instance, **kwargs):
    if instance.pk:  # Existing transaction being updated
        old_transaction = Transaction.objects.get(pk=instance.pk)
        if old_transaction.amount != instance.amount or old_transaction.transaction_type != instance.transaction_type:
            instance.wallet.update_from_transactions()
            if old_transaction.transaction_type == 'ADD_INCOME' and instance.transaction_type != 'ADD_INCOME':
                instance.wallet.total_income -= old_transaction.amount  # Remove old income if type changes
            elif instance.transaction_type == 'ADD_INCOME' and old_transaction.transaction_type != 'ADD_INCOME':
                instance.wallet.total_income += instance.amount  # Add new income if type changes to ADD_INCOME
            instance.wallet.save()


@receiver(pre_delete, sender=Transaction)
def prevent_transaction_delete(sender, instance, **kwargs):
    print(f"Attempted deletion of transaction {instance.id} for wallet {instance.wallet.user.username} at {timezone.now()}")