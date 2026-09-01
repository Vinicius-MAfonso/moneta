from django.contrib import admin

from .models import Account, CreditCardBill, CreditCardDetails


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'updated_at')
    list_display = ('name', 'user', 'type', 'institution', 'balance', 'active')
    list_filter = ('type', 'active')
    search_fields = ('name', 'institution', 'user__username')
    ordering = ('name',)
    list_per_page = 25


@admin.register(CreditCardDetails)
class CreditCardDetailsAdmin(admin.ModelAdmin):
    list_display = ('account', 'limit', 'available_limit', 'closing_day', 'due_day')
    search_fields = ('account__name', 'account__user__username')
    list_per_page = 25


@admin.register(CreditCardBill)
class CreditCardBillAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'updated_at')
    list_display = ('account', 'period_date', 'status', 'closing_date', 'due_date', 'is_due_tomorrow_notified')
    list_filter = ('status', 'is_due_tomorrow_notified')
    search_fields = ('account__name', 'account__user__username')
    ordering = ('-period_date',)
    list_per_page = 25