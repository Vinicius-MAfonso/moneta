from django.contrib import admin

from .models import Investment


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    exclude = ('user',)
    list_display = ('name', 'user', 'account', 'type', 'quantity', 'current_price', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('name', 'user__username', 'account__name')
    ordering = ('-created_at',)
    
    
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)