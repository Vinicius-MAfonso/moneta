from django.contrib import admin

from .models import Category, RecurringTransaction, Tag, Transaction, Transfer


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'type', 'parent', 'created_at')
    list_filter = ('type',)
    search_fields = ('name', 'user__username')


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'color')
    search_fields = ('name', 'user__username')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('description', 'user', 'category', 'type', 'amount', 'date', 'status')
    list_filter = ('type', 'status', 'date')
    search_fields = ('description', 'user__username', 'category__name')
    ordering = ('-date',)


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('description', 'user', 'from_account', 'to_account', 'amount', 'date')
    search_fields = ('description', 'user__username')
    ordering = ('-date',)


@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_display = ('description', 'user', 'category', 'account', 'credit_card', 'amount', 'type', 'frequency', 'active')
    list_filter = ('type', 'frequency', 'active')
    search_fields = ('description', 'user__username', 'category__name')
