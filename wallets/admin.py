from django.contrib import admin

from .models import Account, CreditCard


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    exclude = ('user',)
    list_display = ('name', 'type', 'institution', 'balance', 'active')
    list_filter = ('type', 'active')
    search_fields = ('name', 'institution', 'user__username')
    ordering = ('name',)

    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(CreditCard)
class CreditCardAdmin(admin.ModelAdmin):
    exclude = ('user',)
    readonly_fields = ('available_limit',)
    list_display = ('name', 'institution', 'limit', 'available_limit', 'closing_day', 'due_day', 'active')
    list_filter = ('active',)
    search_fields = ('name', 'institution', 'user__username')
    ordering = ('name',)
    

    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)