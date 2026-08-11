from django.urls import path

from . import views

app_name = 'users_web'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('settings/', views.settings_view, name='settings'),
    path('import/', views.import_ofx_view, name='import_ofx'),
    path('import/review/', views.import_review_view, name='import_review'),
]
