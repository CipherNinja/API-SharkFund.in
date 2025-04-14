from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    # Define the fields for the detail view
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('address', 'mobile_number')}),
    )

    # Define the fields for the create user form
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('address', 'mobile_number')}),
    )

    # Fields to display in the user list view
    list_display = UserAdmin.list_display + ('address', 'mobile_number')

admin.site.register(CustomUser, CustomUserAdmin)
