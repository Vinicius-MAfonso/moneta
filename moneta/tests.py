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


class CronWakeTestCase(TestCase):
    def test_cron_wake_unauthorized_without_header(self):
        response = self.client.post(reverse('cron_wake'))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {'error': 'Unauthorized'})

    @override_settings(CRON_SECRET='test-secret-token-123')
    def test_cron_wake_unauthorized_with_wrong_header(self):
        response = self.client.post(
            reverse('cron_wake'),
            HTTP_AUTHORIZATION='Bearer wrong-token'
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(CRON_SECRET='test-secret-token-123')
    @patch('django_q.tasks.async_task')
    def test_cron_wake_authorized(self, mock_async_task):
        response = self.client.post(
            reverse('cron_wake'),
            HTTP_AUTHORIZATION='Bearer test-secret-token-123'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'tasks_queued': 5})
        self.assertEqual(mock_async_task.call_count, 5)
