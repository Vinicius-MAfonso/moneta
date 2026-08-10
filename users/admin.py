from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informações Adicionais', {'fields': ('photo_url', 'currency', 'timezone')}),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    list_display = ('username', 'email', 'currency', 'timezone', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'currency')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_per_page = 25