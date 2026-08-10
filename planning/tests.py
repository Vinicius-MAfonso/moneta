from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from moneta.common import TransactionType
from planning.models import Budget, Goal
from transactions.models import Category

User = get_user_model()


class PlanningWebTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='planner', password='password123')
        self.client.force_login(self.user)
        self.category = Category.objects.create(user=self.user, name='Alimentação', type=TransactionType.EXPENSE)

    def test_planning_list_view(self):
        res = self.client.get('/planning/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Planejamento')

    def test_budget_web_crud(self):
        payload = {
            'category': str(self.category.id),
            'amount': '1000.00',
            'start_date': '2026-08-01',
            'end_date': '2026-08-31'
        }
        res = self.client.post('/planning/budget/create/', data=payload)
        self.assertEqual(res.status_code, 302)

        budget = Budget.objects.get(category=self.category)
        self.assertEqual(budget.amount, Decimal('1000.00'))

        res = self.client.get(f'/planning/budget/{budget.id}/confirm-delete/')
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f'/planning/budget/{budget.id}/delete/')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Budget.objects.filter(id=budget.id).exists())

    def test_goal_web_crud(self):
        goal_payload = {
            'name': 'Viagem de Férias',
            'target_amount': '5000.00',
            'current_amount': '500.00',
            'start_date': '2026-08-01',
            'end_date': '2026-12-31'
        }
        res = self.client.post('/planning/goal/create/', data=goal_payload)
        self.assertEqual(res.status_code, 302)

        goal = Goal.objects.get(name='Viagem de Férias')
        self.assertEqual(goal.target_amount, Decimal('5000.00'))

        res = self.client.get(f'/planning/goal/{goal.id}/confirm-delete/')
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f'/planning/goal/{goal.id}/delete/')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Goal.objects.filter(id=goal.id).exists())
