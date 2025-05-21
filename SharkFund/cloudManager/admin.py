from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Wallet, Transaction, PaymentDetail, MonthlyIncome, PaymentScreenshot
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html

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

        if not wallet and 'wallet' in self.data:
            try:
                wallet_id = self.data['wallet']
                wallet = Wallet.objects.get(id=wallet_id)
            except (Wallet.DoesNotExist, ValueError, KeyError):
                pass

        if transaction_type == 'WITHDRAWAL' and wallet:
            try:
                current_balance = wallet.calculate_balance()

                # Adjust balance if editing an existing withdrawal
                if self.instance.pk and self.instance.transaction_type == 'WITHDRAWAL':
                    current_balance += self.instance.amount

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
    form = TransactionAdminForm
    extra = 1
    fields = ('amount', 'transaction_type','status', 'timestamp', 'description')
    readonly_fields = ('timestamp',)

# Inline for PaymentDetail model within CustomUser
class PaymentDetailInline(admin.StackedInline):
    model = PaymentDetail
    extra = 0  # No extra empty forms since it's one-to-one
    can_delete = False  # Prevent deletion since it's one-to-one

    fieldsets = (
        ('Bank Account Info', {
            'fields': (('account_holder_name', 'account_number', 'ifsc_code'),),
        }),
        ('UPI Details', {
            'fields': ('upi_id',),
        }),
        ('Card Details', {
            'fields': (('card_number', 'name_on_card'), ('expiry_date', 'cvv')),
        }),
    )

# Inline for Wallet model within CustomUser
class WalletInline(admin.TabularInline):
    model = Wallet
    extra = 0
    fields = ()
    readonly_fields = ('total_income', 'total_withdrawal', 'wallet_balance', 'created_at')
    inlines = [TransactionInline]


class MonthlyIncomeInline(admin.TabularInline):
    model = MonthlyIncome
    extra = 1  # Show one empty form for adding a new record
    fields = ('month', 'monthly_payout', 'monthly_income', 'total_income')
    readonly_fields = ('created_at',)

# Custom User Admin with referral properties, Wallet inline, and PaymentDetail inline
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'name', 'email', 'status', 'total_referrals', 'active_referrals', 'total_team', 'active_team', 'is_staff')
    list_filter = ('status', 'is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'email', 'mobile_number')
    ordering = ('-join_date',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('name', 'email', 'address', 'mobile_number', 'referred_by')}),
        ('Permissions', {'fields': ('status', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('join_date', 'last_active')}),
    )

    inlines = [WalletInline, PaymentDetailInline, MonthlyIncomeInline]

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
    active_team.short_description = 'Active Team'

# Wallet Admin with Transaction inline
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_income', 'total_withdrawal', 'wallet_balance', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('total_income', 'total_withdrawal', 'wallet_balance', 'created_at')
    fields = ()
    inlines = [TransactionInline]


@admin.register(PaymentScreenshot)
class PaymentScreenshotAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'created_at', 'screenshot_preview')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__email')
    fields = ('user', 'amount', 'screenshot', 'status', 'created_at')
    readonly_fields = ('created_at', 'screenshot_preview')
    list_editable = ('status',)
    ordering = ('-created_at',)

    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html('<img src="{}" style="max-height: 100px;"/>', obj.screenshot.url)
        return "No screenshot"
    screenshot_preview.short_description = 'Screenshot'
# Register the models with their admins
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Wallet, WalletAdmin)
admin.site.register(PaymentDetail)