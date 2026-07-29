from django.contrib import admin

from .models import Investment


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'account', 'type', 'quantity', 'current_price', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('name', 'user__username', 'account__name')
    ordering = ('-created_at',)
