from django.contrib import admin

from .models import Budget, Goal, GoalTransaction


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('category', 'user', 'amount', 'start_date', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = ('category__name', 'user__username')


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'target_amount', 'current_amount', 'start_date', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = ('name', 'user__username')


@admin.register(GoalTransaction)
class GoalTransactionAdmin(admin.ModelAdmin):
    list_display = ('goal', 'transaction', 'amount', 'created_at')
    search_fields = ('goal__name', 'transaction__description')
