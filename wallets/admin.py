from django.contrib import admin

from .models import Account, CreditCard


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'type', 'institution', 'balance', 'active')
    list_filter = ('type', 'active')
    search_fields = ('name', 'institution', 'user__username')
    ordering = ('name',)


@admin.register(CreditCard)
class CreditCardAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'institution', 'limit', 'available_limit', 'closing_day', 'due_day', 'active')
    list_filter = ('active',)
    search_fields = ('name', 'institution', 'user__username')
    ordering = ('name',)
