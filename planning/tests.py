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
        self.category, _ = Category.objects.get_or_create(user=self.user, name='Alimentação', defaults={'type': TransactionType.EXPENSE})

    def test_planning_list_view(self):
        Goal.objects.create(
            user=self.user,
            name='Reserva de Emergência',
            target_amount=Decimal('10000.00'),
            current_amount=Decimal('2500.00'),
            start_date='2026-08-01',
            end_date='2026-12-31'
        )
        res = self.client.get('/planning/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Planejamento')
        self.assertContains(res, 'Reserva de Emergência')
        self.assertEqual(len(res.context['goals']), 1)
        self.assertEqual(res.context['goals'][0].percentage, 25.0)

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

    def test_calculate_budget_progress(self):
        from planning.services import calculate_budget_progress
        from transactions.models import Transaction
        from wallets.models import Account

        account = Account.objects.create(
            user=self.user, name='Conta', type=Account.Types.CHECKING,
            balance=Decimal('1000.00'), initial_balance=Decimal('1000.00')
        )
        
        # Orçamento recorrente mensal
        budget = Budget.objects.create(
            user=self.user, category=self.category, amount=Decimal('500.00'),
            is_recurring=True, start_date='2026-08-01'
        )
        
        # Gasto em Agosto
        Transaction.objects.create(
            user=self.user, account=account, category=self.category,
            description='Mercado Agosto', amount=Decimal('400.00'), date='2026-08-10',
            status=Transaction.Statuses.COMPLETED
        )

        # Progresso em Agosto (80%)
        progress_aug = calculate_budget_progress(budget, reference_date='2026-08-15')
        self.assertEqual(progress_aug['spent'], Decimal('400.00'))
        self.assertEqual(progress_aug['percentage'], Decimal('80.00'))
        self.assertEqual(progress_aug['remaining'], Decimal('100.00'))
        self.assertTrue(progress_aug['is_warning'])
        self.assertFalse(progress_aug['is_over_budget'])

        # Progresso em Setembro (reset automático para 0% porque não há gastos em Setembro ainda)
        progress_sep = calculate_budget_progress(budget, reference_date='2026-09-01')
        self.assertEqual(progress_sep['spent'], Decimal('0.00'))
        self.assertEqual(progress_sep['percentage'], Decimal('0.00'))
        self.assertEqual(progress_sep['remaining'], Decimal('500.00'))
        self.assertFalse(progress_sep['is_warning'])

    def test_deposit_to_goal(self):
        from planning.services import deposit_to_goal
        
        goal = Goal.objects.create(
            user=self.user,
            name='Carro Novo',
            target_amount=Decimal('50000.00'),
            current_amount=Decimal('1000.00'),
            start_date='2026-08-01',
            end_date='2027-08-01'
        )
        
        success = deposit_to_goal(goal, Decimal('500.00'))
        self.assertTrue(success)
        
        goal.refresh_from_db()
        self.assertEqual(goal.current_amount, Decimal('1500.00'))
        
        # Testar valor inválido
        success = deposit_to_goal(goal, Decimal('-100.00'))
        self.assertFalse(success)
        goal.refresh_from_db()
        self.assertEqual(goal.current_amount, Decimal('1500.00'))

    def test_get_active_budgets(self):
        from datetime import date

        from planning.services import get_active_budgets
        
        # Orçamento mensal recorrente
        Budget.objects.create(
            user=self.user, category=self.category, amount=Decimal('500.00'),
            is_recurring=True, start_date=date(2026, 8, 1)
        )
        
        active_budgets = get_active_budgets(self.user, reference_date=date(2026, 8, 15))
        self.assertEqual(len(active_budgets), 1)
        self.assertEqual(active_budgets[0]['budget'].amount, Decimal('500.00'))

        # Em setembro, o orçamento recorrente continua ativo
        active_budgets_sep = get_active_budgets(self.user, reference_date=date(2026, 9, 10))
        self.assertEqual(len(active_budgets_sep), 1)

    def test_budget_overlapping_validation(self):
        from django.core.exceptions import ValidationError
        
        # Orçamento recorrente
        Budget.objects.create(
            user=self.user, category=self.category, amount=Decimal('500.00'),
            is_recurring=True, start_date='2026-08-01'
        )
        
        # Criar outro orçamento recorrente para a mesma categoria deve falhar
        duplicate_budget = Budget(
            user=self.user, category=self.category, amount=Decimal('300.00'),
            is_recurring=True, start_date='2026-09-01'
        )
        with self.assertRaises(ValidationError):
            duplicate_budget.save()
