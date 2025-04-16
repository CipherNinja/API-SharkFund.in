from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Wallet, Transaction

# Inline for Transaction model within Wallet
class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 1  # Number of empty forms to display
    fields = ('amount', 'transaction_type', 'timestamp', 'description')
    readonly_fields = ('timestamp',)  # Timestamp is set automatically

# Inline for Wallet model within CustomUser
class WalletInline(admin.TabularInline):
    model = Wallet
    extra = 0  # No extra empty forms since it's one-to-one
    fields = ()  # No editable fields
    readonly_fields = ('total_income', 'total_withdrawal', 'wallet_balance', 'created_at')  # All fields read-only
    inlines = [TransactionInline]

# Custom User Admin with referral properties and Wallet inline
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'total_referrals', 'active_referrals', 'total_team', 'active_team', 'is_staff')
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