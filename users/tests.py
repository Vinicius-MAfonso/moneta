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

    def test_login_redirect_safe_internal_url(self):
        self.client.logout()
        res = self.client.post('/users/login/?next=/wallets/', {'username': 'profileuser', 'password': 'password123'})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/wallets/')

    def test_login_redirect_unsafe_external_url(self):
        self.client.logout()
        res = self.client.post('/users/login/?next=https://evil.com/phishing', {'username': 'profileuser', 'password': 'password123'})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse('dashboard'))

        self.client.logout()
        res = self.client.post('/users/login/?next=//malicious-site.com', {'username': 'profileuser', 'password': 'password123'})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse('dashboard'))


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

    def test_save_push_subscription_invalid_json(self):
        res = self.client.post(
            reverse('users_web:save_push_subscription'),
            data='{invalid json payload',
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Falha ao processar assinatura push.')


class ImportStatementTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='importuser', password='password123')
        self.client.force_login(self.user)

        from moneta.common import TransactionType
        from transactions.models import Category
        from wallets.models import Account

        self.account = Account.objects.create(
            user=self.user,
            name='Conta Principal',
            type=Account.Types.CHECKING,
            initial_balance=1000.00,
            balance=1000.00
        )
        self.category_food, _ = Category.objects.get_or_create(
            user=self.user,
            name='Alimentação',
            defaults={
                'type': TransactionType.EXPENSE,
                'icon': '🍔'
            }
        )
        self.category_salary, _ = Category.objects.get_or_create(
            user=self.user,
            name='Salário',
            defaults={
                'type': TransactionType.INCOME,
                'icon': '💰'
            }
        )

    def test_parse_csv_variations(self):
        from users.services import parse_csv_file

        # Nubank style
        nubank_csv = "Data,Valor,Identificador,Descrição\n2026-08-01,-45.90,id1,iFood Restaurante\n2026-08-05,2500.00,id2,Transferência Recebida"
        txs = parse_csv_file(nubank_csv)
        self.assertEqual(len(txs), 2)
        self.assertEqual(txs[0]['date'], '01/08/2026')
        self.assertEqual(txs[0]['payee'], 'iFood Restaurante')
        self.assertEqual(txs[0]['type'], 'despesa')
        self.assertEqual(txs[0]['amount'], '45.90')
        self.assertEqual(txs[1]['type'], 'receita')
        self.assertEqual(txs[1]['amount'], '2500.00')

        # Inter style (semicolon + BR decimal)
        inter_csv = "Data Lançamento;Histórico;Descrição;Valor;Saldo\n02/08/2026;Pix Enviado;Supermercado Guanabara;-150,50;1.200,00"
        txs_inter = parse_csv_file(inter_csv)
        self.assertEqual(len(txs_inter), 1)
        self.assertEqual(txs_inter[0]['date'], '02/08/2026')
        self.assertEqual(txs_inter[0]['type'], 'despesa')
        self.assertEqual(txs_inter[0]['amount'], '150.50')

    def test_enrich_suggestions_and_duplicate_detection(self):
        from decimal import Decimal

        from transactions.models import Transaction
        from users.services import enrich_transactions_with_suggestions_and_duplicates

        # Create prior transaction to populate habit history
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            category=self.category_food,
            amount=Decimal('45.90'),
            date='2026-08-01',
            description='iFood Restaurante',
            status=Transaction.Statuses.COMPLETED
        )

        test_items = [
            {
                'id': 'tx-1',
                'date': '01/08/2026',
                'date_iso': '2026-08-01',
                'payee': 'iFood Restaurante',
                'amount': '45.90',
                'type': 'despesa'
            },
            {
                'id': 'tx-2',
                'date': '10/08/2026',
                'date_iso': '2026-08-10',
                'payee': 'iFood Shopping',
                'amount': '80.00',
                'type': 'despesa'
            }
        ]

        enriched = enrich_transactions_with_suggestions_and_duplicates(self.user, test_items)

        # tx-1 is a duplicate (same amount and date as existing transaction) and gets a suggestion
        self.assertTrue(enriched[0]['is_duplicate'])
        self.assertEqual(enriched[0]['suggested_category_id'], str(self.category_food.id))

        # tx-2 is new (not duplicate) but receives smart suggestion via name similarity
        self.assertFalse(enriched[1]['is_duplicate'])
        self.assertEqual(enriched[1]['suggested_category_id'], str(self.category_food.id))

    def test_import_full_flow(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from transactions.models import Transaction

        csv_content = b"Data,Descricao,Valor\n05/08/2026,Aluguel Apartamento,-1200.00\n"
        upload_file = SimpleUploadedFile("extrato.csv", csv_content, content_type="text/csv")

        # 1. File upload
        res = self.client.post(reverse('users_web:import_file'), {'file': upload_file})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse('users_web:import_review'))

        # 2. Review screen GET
        res_review = self.client.get(reverse('users_web:import_review'))
        self.assertEqual(res_review.status_code, 200)
        self.assertContains(res_review, 'Aluguel Apartamento')
        self.assertIn('description_habits_json', res_review.context)
        self.assertIsInstance(res_review.context['description_habits_json'], str)

        # 3. Save import POST
        session = self.client.session
        tx_id = session['import_transactions'][0]['id']

        post_data = {
            'account_id': str(self.account.id),
            f'category_{tx_id}': str(self.category_food.id),
            f'description_{tx_id}': 'Aluguel Mensal',
        }
        res_save = self.client.post(reverse('users_web:import_review'), post_data)
        self.assertEqual(res_save.status_code, 302)

        # Verify transaction was saved to the database
        self.assertTrue(Transaction.objects.filter(user=self.user, description='Aluguel Mensal').exists())
        self.account.refresh_from_db()
        # Initial balance 1000 - 1200 expense = -200
        self.assertEqual(self.account.balance, -200.00)

