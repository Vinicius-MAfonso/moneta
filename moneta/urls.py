from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from .views import (
    cron_check_alerts_view,
    cron_notify_bills_view,
    cron_notify_budgets_view,
    cron_notify_transactions_view,
    cron_process_recurring_view,
    cron_wake_view,
    dashboard_view,
    export_transactions_csv_view,
    health_check_view,
    reports_view,
)

urlpatterns = [
    path('healthz/', health_check_view, name='health_check'),
    path('internal/cron/process-recurring/', cron_process_recurring_view, name='cron_process_recurring'),
    path('internal/cron/notify-bills/', cron_notify_bills_view, name='cron_notify_bills'),
    path('internal/cron/notify-budgets/', cron_notify_budgets_view, name='cron_notify_budgets'),
    path('internal/cron/notify-transactions/', cron_notify_transactions_view, name='cron_notify_transactions'),
    path('internal/cron/check-alerts/', cron_check_alerts_view, name='cron_check_alerts'),
    path('internal/cron/wake/', cron_wake_view, name='cron_wake'),
    path('internal/cron/run-all/', cron_wake_view, name='cron_run_all'),
    path('admin/', admin.site.urls),
    
    # Web / HTMX Routes
    path('', dashboard_view, name='dashboard'),
    path('reports/', reports_view, name='reports'),
    path('reports/export/csv/', export_transactions_csv_view, name='export_csv'),
    path('transactions/', include('transactions.urls_web')),
    path('wallets/', include('wallets.urls_web')),
    path('planning/', include('planning.urls_web')),
    path('users/', include('users.urls_web')),

    # PWA files
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json'), name='manifest'),
    path('serviceworker.js', TemplateView.as_view(template_name='serviceworker.js', content_type='application/javascript'), name='serviceworker'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
