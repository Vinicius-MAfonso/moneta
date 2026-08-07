from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from transactions.models import Category, Transaction
from wallets.models import Account
from planning.models import Budget, Goal, GoalTransaction
from moneta.common import TransactionType

User = get_user_model()


class PlanningAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='planner', password='password123')
        self.client.force_login(self.user)
        self.category = Category.objects.create(user=self.user, name='Alimentação', type=TransactionType.EXPENSE)
        self.account = Account.objects.create(user=self.user, name='Conta Corrente', type=Account.Types.CHECKING)
        self.transaction = Transaction.objects.create(
            user=self.user,
            account=self.account,
            category=self.category,
            description='Supermercado',
            amount=Decimal('200.00'),
            date='2026-08-01',
            status=Transaction.Statuses.COMPLETED
        )

    def test_budget_crud(self):
        payload = {
            'category': str(self.category.id),
            'amount': '1000.00',
            'start_date': '2026-08-01',
            'end_date': '2026-08-31'
        }
        res = self.client.post('/api/planning/budgets', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        budget_id = res.json()['id']

        res = self.client.get('/api/planning/budgets')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)

        res = self.client.get(f'/api/planning/budgets/{budget_id}')
        self.assertEqual(res.status_code, 200)

        res = self.client.delete(f'/api/planning/budgets/{budget_id}')
        self.assertEqual(res.status_code, 204)
        self.assertEqual(Budget.objects.filter(id=budget_id).count(), 0)

    def test_goal_and_goal_transaction_crud(self):
        goal_payload = {
            'name': 'Viagem de Férias',
            'target_amount': '5000.00',
            'current_amount': '0.00',
            'start_date': '2026-08-01',
            'end_date': '2026-12-31'
        }
        res = self.client.post('/api/planning/goals', data=goal_payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        goal_id = res.json()['id']

        # Goal Transaction Link
        gt_payload = {
            'goal': goal_id,
            'transaction': str(self.transaction.id),
            'amount': '100.00'
        }
        res = self.client.post('/api/planning/goal-transactions', data=gt_payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        link_id = res.json()['id']

        # Verify Goal current_amount updated via model save trigger
        goal = Goal.objects.get(id=goal_id)
        self.assertEqual(goal.current_amount, Decimal('100.00'))

        res = self.client.delete(f'/api/planning/goal-transactions/{link_id}')
        self.assertEqual(res.status_code, 204)

        # Verify Goal current_amount reverted on link delete
        goal.refresh_from_db()
        self.assertEqual(goal.current_amount, Decimal('0.00'))
