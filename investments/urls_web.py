from django.urls import path
from . import views

app_name = 'investments_web'

urlpatterns = [
    path('', views.investment_list_view, name='list'),
    path('create/', views.investment_create_view, name='create'),
    path('<uuid:pk>/confirm-delete/', views.investment_confirm_delete_view, name='confirm_delete'),
    path('<uuid:pk>/delete/', views.investment_delete_view, name='delete'),
]
