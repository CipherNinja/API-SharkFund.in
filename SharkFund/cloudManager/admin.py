from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Wallet, Transaction
from django import forms
from django.core.exceptions import ValidationError

# Custom form for Transaction model to handle validation errors
class TransactionAdminForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ('amount', 'transaction_type', 'description')

    def clean(self):
        cleaned_data = super().clean()
        transaction_type = cleaned_data.get('transaction_type')
        amount = cleaned_data.get('amount')
        wallet = self.instance.wallet if self.instance and self.instance.pk else None

        # If this is a new transaction, wallet should be set via the inline
        if not wallet and 'wallet' in self.data:
            try:
                wallet_id = self.data['wallet']
                wallet = Wallet.objects.get(id=wallet_id)
            except (Wallet.DoesNotExist, ValueError, KeyError):
                pass  # Wallet will be validated by the parent form

        if transaction_type == 'WITHDRAWAL' and wallet:
            try:
                current_balance = wallet.calculate_balance()
                if amount > current_balance:
                    raise ValidationError(
                        f"Withdrawal amount ({amount}) exceeds available balance ({current_balance})."
                    )
            except Exception as e:
                raise ValidationError(f"Error calculating balance: {str(e)}")

        return cleaned_data

# Inline for Transaction model within Wallet
class TransactionInline(admin.TabularInline):
    model = Transaction
    form = TransactionAdminForm  # Use the custom form
    extra = 1  # Number of empty forms to display
    fields = ('amount', 'transaction_type', 'timestamp', 'description')
    readonly_fields = ('timestamp',)  # Corrected: Proper tuple with 'timestamp' as the only readonly field

# Inline for Wallet model within CustomUser
class WalletInline(admin.TabularInline):
    model = Wallet
    extra = 0  # No extra empty forms since it's one-to-one
    fields = ()  # No editable fields
    readonly_fields = ('total_income', 'total_withdrawal', 'wallet_balance', 'created_at')  # All fields read-only
    inlines = [TransactionInline]

# Custom User Admin with referral properties and Wallet inline
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'name', 'email', 'total_referrals', 'active_referrals', 'total_team', 'active_team', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'email', 'mobile_number')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('email', 'address', 'mobile_number', 'referred_by')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('join_date', 'last_active')}),
    )
    readonly_fields = ('join_date', 'last_active', 'total_referrals', 'active_referrals', 'total_team', 'active_team')

    inlines = [WalletInline]

    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly for existing objects."""
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj:  # Editing an existing object
            return readonly_fields + ('username', 'email', 'referred_by')
        return readonly_fields

    def total_referrals(self, obj):
        return obj.total_referrals
    total_referrals.short_description = 'Total Referrals'

    def active_referrals(self, obj):
        return obj.active_referrals
    active_referrals.short_description = 'Active Referrals'

    def total_team(self, obj):
        return obj.total_team
    total_team.short_description = 'Total Team'

    def active_team(self, obj):
        return obj.active_team
    positions = ['Long', 'Short']
    active_team.short_description = 'Active Team'

# Wallet Admin with Transaction inline
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_income', 'total_withdrawal', 'wallet_balance', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('total_income', 'total_withdrawal', 'wallet_balance', 'created_at')  # All fields read-only
    fields = ()  # No editable fields
    inlines = [TransactionInline]

# Register the models with their admins
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Wallet, WalletAdmin)