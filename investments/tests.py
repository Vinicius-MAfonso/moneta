from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from investments.models import Investment
from wallets.models import Account

User = get_user_model()


class InvestmentsWebTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='investor', password='password123')
        self.client.force_login(self.user)
        self.account = Account.objects.create(user=self.user, name='Corretora Y', type=Account.Types.INVESTMENT)

    def test_investment_web_crud(self):
        res = self.client.get('/investments/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Carteira de Investimentos')

        payload = {
            'account': str(self.account.id),
            'name': 'PETR4',
            'type': Investment.Types.STOCK,
            'quantity': '100.00',
            'average_price': '30.50',
            'current_price': '35.00'
        }
        res = self.client.post('/investments/create/', data=payload)
        self.assertEqual(res.status_code, 302)

        inv = Investment.objects.get(name='PETR4')
        self.assertEqual(inv.user, self.user)
        self.assertEqual(inv.quantity, Decimal('100.00'))

        res = self.client.get(f'/investments/{inv.id}/confirm-delete/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Excluir Ativo')

        res = self.client.post(f'/investments/{inv.id}/delete/')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Investment.objects.filter(id=inv.id).exists())
