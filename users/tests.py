from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UsersAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='profileuser', password='password123', email='user@example.com')
        self.client.force_login(self.user)

    def test_get_and_update_profile(self):
        res = self.client.get('/api/users/me')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['username'], 'profileuser')

        update_payload = {
            'first_name': 'João',
            'last_name': 'Silva',
            'currency': 'USD',
            'timezone': 'UTC'
        }
        res = self.client.put('/api/users/me', data=update_payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['first_name'], 'João')
        self.assertEqual(res.json()['currency'], 'USD')

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'João')
        self.assertEqual(self.user.currency, 'USD')
