from django.contrib import admin

from .models import Category, RecurringTransaction, Tag, Transaction, Transfer


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_select_related = ('user', 'parent')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('parent',)
    list_display = ('name', 'user', 'type', 'parent', 'created_at')
    list_filter = ('type',)
    search_fields = ('name', 'user__username')
    ordering = ('name',)
    list_per_page = 25


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_select_related = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    list_display = ('name', 'user', 'color')
    search_fields = ('name', 'user__username')
    ordering = ('name',)
    list_per_page = 25


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_select_related = ('user', 'account', 'category', 'recurring', 'bill')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('account', 'category', 'recurring')
    filter_horizontal = ('tags',)
    list_display = ('description', 'user', 'category', 'type', 'amount', 'date', 'status')
    list_filter = ('status', 'date')
    search_fields = ('description', 'user__username', 'category__name', 'tags__name')
    ordering = ('-date',)
    list_per_page = 25
    date_hierarchy = 'date'


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_select_related = (
        'user',
        'out_transaction__account',
        'in_transaction__account',
    )
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('out_transaction', 'in_transaction')
    list_display = ('out_transaction', 'in_transaction', 'user', 'created_at')
    ordering = ('-created_at',)
    list_per_page = 25


@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_select_related = ('user', 'category', 'account', 'target_account')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('category', 'account')
    list_display = ('description', 'user', 'category', 'account', 'amount', 'type', 'frequency', 'active')
    list_filter = ('frequency', 'active')
    search_fields = ('description', 'user__username', 'category__name')
    ordering = ('-created_at',)
    list_per_page = 25
    date_hierarchy = 'start_date'


