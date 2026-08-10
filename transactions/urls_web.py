from django.urls import path

from . import views

app_name = 'transactions_web'

urlpatterns = [
    path('', views.transaction_list_view, name='list'),
    path('create/', views.transaction_create_view, name='create'),
    path('<uuid:pk>/edit/', views.transaction_update_view, name='edit'),
    path('<uuid:pk>/confirm-delete/', views.transaction_confirm_delete_view, name='confirm_delete'),
    path('<uuid:pk>/delete/', views.transaction_delete_view, name='delete'),
    

    
    # Categories & Tags
    path('categories/', views.category_list_view, name='category_list'),
    path('categories/create/', views.category_create_view, name='category_create'),
    path('categories/<uuid:pk>/confirm-delete/', views.category_confirm_delete_view, name='category_confirm_delete'),
    path('categories/<uuid:pk>/delete/', views.category_delete_view, name='category_delete'),
    path('tags/create/', views.tag_create_view, name='tag_create'),
    path('tags/<uuid:pk>/confirm-delete/', views.tag_confirm_delete_view, name='tag_confirm_delete'),
    path('tags/<uuid:pk>/delete/', views.tag_delete_view, name='tag_delete'),

    # Recurring
    path('recurring/', views.recurring_list_view, name='recurring_list'),
    path('recurring/create/', views.recurring_create_view, name='recurring_create'),
    path('recurring/<uuid:pk>/confirm-delete/', views.recurring_confirm_delete_view, name='recurring_confirm_delete'),
    path('recurring/<uuid:pk>/delete/', views.recurring_delete_view, name='recurring_delete'),

    # Transfers
    path('transfers/create/', views.transfer_create_view, name='transfer_create'),
]
