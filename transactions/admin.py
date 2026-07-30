from django.contrib import admin

from .models import Category, RecurringTransaction, Tag, Transaction, Transfer


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    exclude = ('user',)
    list_display = ('name', 'user', 'type', 'parent', 'created_at')
    list_filter = ('type',)
    search_fields = ('name', 'user__username')

    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    exclude = ('user',)
    list_display = ('name', 'user', 'color')
    search_fields = ('name', 'user__username')
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    exclude = ('user',)
    list_display = ('description', 'user', 'category', 'type', 'amount', 'date', 'status')
    list_filter = ('type', 'status', 'date')
    search_fields = ('description', 'user__username', 'category__name')
    ordering = ('-date',)
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    exclude = ('user',)
    list_display = ('description', 'user', 'from_account', 'to_account', 'amount', 'date')
    search_fields = ('description', 'user__username')
    ordering = ('-date',)
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    exclude = ('user',)
    list_display = ('description', 'user', 'category', 'account', 'credit_card', 'amount', 'type', 'frequency', 'active')
    list_filter = ('type', 'frequency', 'active')
    search_fields = ('description', 'user__username', 'category__name')
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)
