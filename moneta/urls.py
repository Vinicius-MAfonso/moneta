from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from .views import dashboard_view

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Web / HTMX Routes
    path('', dashboard_view, name='dashboard'),
    path('transactions/', include('transactions.urls_web')),
    path('wallets/', include('wallets.urls_web')),
    path('planning/', include('planning.urls_web')),
    path('investments/', include('investments.urls_web')),
    path('users/', include('users.urls_web')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
