from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse


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


class DedicatedCronEndpointsTestCase(TestCase):
    @override_settings(CRON_SECRET='test-secret-token-123')
    def test_all_endpoints_reject_unauthorized(self):
        endpoints = [
            'cron_process_recurring',
            'cron_notify_bills',
            'cron_notify_budgets',
            'cron_notify_transactions',
            'cron_check_alerts',
            'cron_wake',
            'cron_run_all',
        ]
        for ep in endpoints:
            # Without auth header
            res1 = self.client.post(reverse(ep))
            self.assertEqual(res1.status_code, 401, f"{ep} did not reject missing auth")

            # With wrong token
            res2 = self.client.post(reverse(ep), HTTP_AUTHORIZATION='Bearer wrong-token')
            self.assertEqual(res2.status_code, 401, f"{ep} did not reject invalid auth")

    @override_settings(CRON_SECRET='test-secret-token-123')
    @patch('transactions.tasks.process_all_recurring_transactions')
    def test_cron_process_recurring_authorized(self, mock_task):
        response = self.client.post(
            reverse('cron_process_recurring'),
            HTTP_AUTHORIZATION='Bearer test-secret-token-123'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'task': 'process_all_recurring_transactions'})
        self.assertEqual(mock_task.call_count, 1)

    @override_settings(CRON_SECRET='test-secret-token-123')
    @patch('wallets.tasks.notify_due_credit_card_bills')
    def test_cron_notify_bills_authorized(self, mock_task):
        response = self.client.post(
            reverse('cron_notify_bills'),
            HTTP_AUTHORIZATION='Bearer test-secret-token-123'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'task': 'notify_due_credit_card_bills'})
        self.assertEqual(mock_task.call_count, 1)

    @override_settings(CRON_SECRET='test-secret-token-123')
    @patch('planning.tasks.notify_budget_warnings')
    def test_cron_notify_budgets_authorized(self, mock_task):
        response = self.client.post(
            reverse('cron_notify_budgets'),
            HTTP_AUTHORIZATION='Bearer test-secret-token-123'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'task': 'notify_budget_warnings'})
        self.assertEqual(mock_task.call_count, 1)

    @override_settings(CRON_SECRET='test-secret-token-123')
    @patch('transactions.tasks.notify_due_transactions')
    def test_cron_notify_transactions_authorized(self, mock_task):
        response = self.client.post(
            reverse('cron_notify_transactions'),
            HTTP_AUTHORIZATION='Bearer test-secret-token-123'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'task': 'notify_due_transactions'})
        self.assertEqual(mock_task.call_count, 1)

    @override_settings(CRON_SECRET='test-secret-token-123')
    @patch('moneta.tasks.check_and_send_alerts')
    def test_cron_check_alerts_authorized(self, mock_task):
        response = self.client.post(
            reverse('cron_check_alerts'),
            HTTP_AUTHORIZATION='Bearer test-secret-token-123'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'task': 'check_and_send_alerts'})
        self.assertEqual(mock_task.call_count, 1)

    @override_settings(CRON_SECRET='test-secret-token-123')
    @patch('transactions.tasks.process_all_recurring_transactions')
    @patch('wallets.tasks.notify_due_credit_card_bills')
    @patch('planning.tasks.notify_budget_warnings')
    @patch('transactions.tasks.notify_due_transactions')
    @patch('moneta.tasks.check_and_send_alerts')
    def test_cron_wake_run_all_authorized(self, m5, m4, m3, m2, m1):
        response = self.client.post(
            reverse('cron_run_all'),
            HTTP_AUTHORIZATION='Bearer test-secret-token-123'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['total'], 5)
        self.assertEqual(len(data['executed_tasks']), 5)
        self.assertEqual(m1.call_count, 1)
        self.assertEqual(m2.call_count, 1)
        self.assertEqual(m3.call_count, 1)
        self.assertEqual(m4.call_count, 1)
        self.assertEqual(m5.call_count, 1)


class SecurityHeadersTestCase(TestCase):
    def test_content_security_policy_header_present(self):
        response = self.client.get(reverse('health_check'))
        self.assertIn('Content-Security-Policy', response.headers)
        csp = response.headers['Content-Security-Policy']
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src", csp)
        self.assertIn("'nonce-", csp)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", csp)
        self.assertNotIn("'unsafe-eval'", csp)
        self.assertIn("style-src", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)

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

