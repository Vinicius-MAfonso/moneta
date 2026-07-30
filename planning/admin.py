from django.contrib import admin

from .models import Budget, Goal, GoalTransaction


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    exclude = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('category',)
    list_display = ('category', 'user', 'amount', 'start_date', 'end_date', 'created_at')
    list_filter = ('start_date', 'end_date')
    search_fields = ('category__name', 'user__username')
    ordering = ('-start_date',)
    list_per_page = 25
    date_hierarchy = 'start_date'

    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    exclude = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    list_display = ('name', 'user', 'target_amount', 'current_amount', 'start_date', 'end_date', 'created_at')
    list_filter = ('start_date', 'end_date')
    search_fields = ('name', 'user__username')
    ordering = ('-start_date',)
    list_per_page = 25
    date_hierarchy = 'start_date'

    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(GoalTransaction)
class GoalTransactionAdmin(admin.ModelAdmin):
    exclude = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('goal', 'transaction')
    list_display = ('goal', 'transaction', 'amount', 'created_at')
    search_fields = ('goal__name', 'transaction__description')
    ordering = ('-created_at',)
    list_per_page = 25

    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)