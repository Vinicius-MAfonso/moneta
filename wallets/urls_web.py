from django.urls import path
from . import views

app_name = 'wallets_web'

urlpatterns = [
    path('', views.account_list_view, name='list'),
    path('create/', views.account_create_view, name='create'),
    path('<uuid:pk>/confirm-delete/', views.account_confirm_delete_view, name='confirm_delete'),
    path('<uuid:pk>/delete/', views.account_delete_view, name='delete'),
]
