from django.urls import path

from . import views

app_name = 'planning_web'

urlpatterns = [
    path('', views.planning_list_view, name='list'),
    path('budget/create/', views.budget_create_view, name='budget_create'),
    path('budget/<uuid:pk>/confirm-delete/', views.budget_confirm_delete_view, name='budget_confirm_delete'),
    path('budget/<uuid:pk>/delete/', views.budget_delete_view, name='budget_delete'),
    path('goal/create/', views.goal_create_view, name='goal_create'),
    path('goal/<uuid:pk>/deposit/', views.goal_deposit_view, name='goal_deposit'),
    path('goal/<uuid:pk>/confirm-delete/', views.goal_confirm_delete_view, name='goal_confirm_delete'),
    path('goal/<uuid:pk>/delete/', views.goal_delete_view, name='goal_delete'),
]
