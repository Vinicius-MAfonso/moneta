import json

from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import PushSubscription

User = get_user_model()


class UsersWebTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='profileuser', password='password123', email='user@example.com')
        self.client.force_login(self.user)

    def test_settings_get_and_update(self):
        res = self.client.get('/users/settings/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Perfil & Configurações')

        update_payload = {
            'first_name': 'João',
            'last_name': 'Silva',
            'email': 'joao@example.com',
        }
        res = self.client.post('/users/settings/', data=update_payload)
        self.assertEqual(res.status_code, 302)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'João')
        self.assertEqual(self.user.last_name, 'Silva')

    def test_login_and_register_views(self):
        self.client.logout()

        res = self.client.get('/users/login/')
        self.assertEqual(res.status_code, 200)

        res = self.client.post('/users/login/', {'username': 'profileuser', 'password': 'password123'})
        self.assertEqual(res.status_code, 302)

        self.client.logout()

        res = self.client.post('/users/register/', {
            'username': 'newuser',
            'first_name': 'Vinicius',
            'last_name': 'Afonso',
            'email': 'new@example.com',
            'password': 'password123',
            'password_confirm': 'password123'
        })
        self.assertEqual(res.status_code, 302)
        new_user = User.objects.get(username='newuser')
        self.assertEqual(new_user.first_name, 'Vinicius')
        self.assertEqual(new_user.last_name, 'Afonso')


class AxesSecurityTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='targetuser', password='correctpassword123', email='target@example.com')

    def test_brute_force_lockout(self):
        for _ in range(4):
            res = self.client.post(reverse('users_web:login'), {'username': 'targetuser', 'password': 'wrongpassword'}, REMOTE_ADDR='127.0.0.1')
            self.assertEqual(res.status_code, 200)

        res = self.client.post(reverse('users_web:login'), {'username': 'targetuser', 'password': 'wrongpassword'}, REMOTE_ADDR='127.0.0.1')
        self.assertEqual(res.status_code, 429)
        self.assertTrue(AccessAttempt.objects.filter(username='targetuser').exists())

        res = self.client.post(reverse('users_web:login'), {'username': 'targetuser', 'password': 'correctpassword123'}, REMOTE_ADDR='127.0.0.1')
        self.assertEqual(res.status_code, 429)


class PushSubscriptionTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='pushuser', password='password123')
        self.client.force_login(self.user)

    def test_save_push_subscription(self):
        payload = {
            'endpoint': 'https://push.example.com/endpoint',
            'keys': {
                'p256dh': 'test_p256dh',
                'auth': 'test_auth'
            }
        }
        res = self.client.post(
            reverse('users_web:save_push_subscription'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(PushSubscription.objects.filter(user=self.user, endpoint='https://push.example.com/endpoint').exists())

    def test_delete_push_subscription(self):
        PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.example.com/endpoint',
            p256dh='test_p256dh',
            auth='test_auth'
        )
        payload = {
            'endpoint': 'https://push.example.com/endpoint'
        }
        res = self.client.post(
            reverse('users_web:delete_push_subscription'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(user=self.user, endpoint='https://push.example.com/endpoint').exists())
