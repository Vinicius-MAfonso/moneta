from django.test import TestCase
from django.contrib.auth import get_user_model

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
            'currency': 'USD',
            'timezone': 'UTC'
        }
        res = self.client.post('/users/settings/', data=update_payload)
        self.assertEqual(res.status_code, 302)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'João')
        self.assertEqual(self.user.last_name, 'Silva')
        self.assertEqual(self.user.currency, 'USD')

    def test_login_and_register_views(self):
        self.client.logout()

        # Renderização da página de Login
        res = self.client.get('/users/login/')
        self.assertEqual(res.status_code, 200)

        # Submissão do Login
        res = self.client.post('/users/login/', {'username': 'profileuser', 'password': 'password123'})
        self.assertEqual(res.status_code, 302)

        self.client.logout()

        # Submissão de Registro
        res = self.client.post('/users/register/', {
            'username': 'newuser',
            'first_name': 'Vinicius',
            'last_name': 'Afonso',
            'email': 'new@example.com',
            'password': 'password123',
            'password_confirm': 'password123',
            'currency': 'BRL'
        })
        self.assertEqual(res.status_code, 302)
        new_user = User.objects.get(username='newuser')
        self.assertEqual(new_user.first_name, 'Vinicius')
        self.assertEqual(new_user.last_name, 'Afonso')
