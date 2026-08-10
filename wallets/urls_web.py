from django.urls import path

from . import views

app_name = 'wallets_web'

urlpatterns = [
    path('', views.account_list_view, name='list'),
    path('create/', views.account_create_view, name='create'),
    path('<uuid:pk>/edit/', views.account_update_view, name='edit'),
    path('<uuid:pk>/reajuste/', views.account_balance_adjustment_view, name='balance_adjustment'),
    path('<uuid:pk>/confirm-delete/', views.account_confirm_delete_view, name='confirm_delete'),
    path('<uuid:pk>/delete/', views.account_delete_view, name='delete'),
    path('cartao/<uuid:account_id>/faturas/', views.bill_list_view, name='bill_list'),
    path('fatura/<uuid:pk>/', views.bill_detail_view, name='bill_detail'),
    path('fatura/<uuid:pk>/pagar/', views.pay_bill_view, name='pay_bill'),
]
