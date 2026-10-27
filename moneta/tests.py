from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone


class HealthCheckTestCase(TestCase):
    def test_health_check_healthy(self):
        response = self.client.get(reverse('health_check'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy', 'database': 'connected'})

    @patch('django.db.connection.ensure_connection')
    def test_health_check_unhealthy(self, mock_ensure):
        mock_ensure.side_effect = Exception("Sensitive DB connection info: host=10.0.0.1 user=secret")
        response = self.client.get(reverse('health_check'))
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data, {'status': 'unhealthy', 'database': 'disconnected'})
        # Ensure sensitive exception details are NOT exposed
        self.assertNotIn('Sensitive', response.content.decode())
        self.assertNotIn('error', data)


class SecurityHeadersTestCase(TestCase):
    def test_content_security_policy_header_present(self):
        response = self.client.get(reverse('health_check'))
        self.assertIn('Content-Security-Policy', response.headers)
        csp = response.headers['Content-Security-Policy']
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src", csp)
        self.assertIn("'unsafe-inline'", csp)
        self.assertIn("'unsafe-eval'", csp)
        self.assertIn("style-src", csp)

    def test_permissions_policy_header_present(self):
        response = self.client.get(reverse('health_check'))
        self.assertIn('Permissions-Policy', response.headers)
        pp = response.headers['Permissions-Policy']
        self.assertIn("camera=()", pp)
        self.assertIn("microphone=()", pp)
        self.assertIn("geolocation=()", pp)
        self.assertIn("payment=()", pp)

    @override_settings(
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
        SECURE_SSL_REDIRECT=False
    )
    def test_hsts_header_in_secure_production(self):
        response = self.client.get(reverse('health_check'), secure=True)
        self.assertIn('Strict-Transport-Security', response.headers)
        hsts = response.headers['Strict-Transport-Security']
        self.assertIn('max-age=31536000', hsts)
        self.assertIn('includeSubDomains', hsts)
        self.assertIn('preload', hsts)

    @override_settings(SECURE_HSTS_SECONDS=0)
    def test_hsts_header_disabled_when_zero(self):
        response = self.client.get(reverse('health_check'), secure=True)
        self.assertNotIn('Strict-Transport-Security', response.headers)

    @override_settings(CONTENT_SECURITY_POLICY="default-src 'none';")
    def test_custom_csp_override(self):
        response = self.client.get(reverse('health_check'))
        self.assertEqual(response.headers.get('Content-Security-Policy'), "default-src 'none';")


class DashboardAndReportsViewsTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='viewtestuser',
            email='viewtest@example.com',
            password='password123'
        )

    def test_dashboard_view_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'moneta/dashboard.html')

    def test_reports_view_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reports'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'moneta/reports.html')
        self.assertIn('report_data', response.context)
        self.assertIn('chart_labels', response.context)
        self.assertIn('pie_data', response.context)

    def test_reports_view_swaps_inverted_dates(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('reports'),
            {'start_date': '2026-10-25', 'end_date': '2026-10-01'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['start_date'], '2026-10-01')
        self.assertEqual(response.context['end_date'], '2026-10-25')

    def test_export_csv_view_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('export_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('\ufeffData,Descrição'))

    def test_on_entry_daily_checks_create_notifications_once_per_day(self):
        from users.models import Notification
        from wallets.models import Account, CreditCardBill

        cc_account = Account.objects.create(
            user=self.user,
            name='Cartão Teste',
            type=Account.Types.CREDIT_CARD,
        )
        tomorrow = timezone.localdate() + timedelta(days=1)
        bill = CreditCardBill.objects.create(
            account=cc_account,
            period_date=date(tomorrow.year, tomorrow.month, 1),
            closing_date=date(tomorrow.year, tomorrow.month, 15),
            due_date=tomorrow,
            status=CreditCardBill.Statuses.CLOSED,
            is_due_tomorrow_notified=False,
            is_closed_notified=True,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        bill.refresh_from_db()
        self.assertTrue(bill.is_due_tomorrow_notified)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.client.session.get('last_daily_check'), str(timezone.localdate()))

        # Subsequent page loads on the same day skip run_user_daily_checks via session gate
        with patch('users.services.run_user_daily_checks') as mock_checks:
            self.client.get(reverse('dashboard'))
            mock_checks.assert_not_called()


