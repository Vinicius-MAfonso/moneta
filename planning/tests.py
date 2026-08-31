from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from moneta.common import TransactionType
from planning.models import Budget, Goal
from planning.services import (
    calculate_budget_progress,
    calculate_budgets_progress_bulk,
    create_budget,
    create_goal,
    deposit_to_goal,
    get_active_budgets,
    get_budgets_with_progress,
)
from transactions.models import Category, Transaction
from wallets.models import Account

User = get_user_model()


class PlanningWebTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='planner', password='password123')
        self.client.force_login(self.user)
        self.category, _ = Category.objects.get_or_create(
            user=self.user,
            name='Alimentação',
            defaults={'type': TransactionType.EXPENSE}
        )

    def test_planning_list_view(self):
        account = Account.objects.create(
            user=self.user,
            name='Poupança Inter',
            type=Account.Types.CHECKING,
            balance=Decimal('5000.00'),
            initial_balance=Decimal('5000.00')
        )
        Goal.objects.create(
            user=self.user,
            account=account,
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
        self.assertContains(res, 'Poupança Inter')
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
        account = Account.objects.create(
            user=self.user, name='Conta', type=Account.Types.CHECKING,
            balance=Decimal('1000.00'), initial_balance=Decimal('1000.00')
        )
        
        # Monthly recurring budget
        budget = Budget.objects.create(
            user=self.user, category=self.category, amount=Decimal('500.00'),
            is_recurring=True, start_date='2026-08-01'
        )
        
        # August expense
        Transaction.objects.create(
            user=self.user, account=account, category=self.category,
            description='Mercado Agosto', amount=Decimal('400.00'), date='2026-08-10',
            status=Transaction.Statuses.COMPLETED
        )

        # August progress (80%)
        progress_aug = calculate_budget_progress(budget, reference_date='2026-08-15')
        self.assertEqual(progress_aug['spent'], Decimal('400.00'))
        self.assertEqual(progress_aug['percentage'], Decimal('80.00'))
        self.assertEqual(progress_aug['remaining'], Decimal('100.00'))
        self.assertTrue(progress_aug['is_warning'])
        self.assertFalse(progress_aug['is_over_budget'])

        # September progress (automatic reset to 0% as there are no September expenses yet)
        progress_sep = calculate_budget_progress(budget, reference_date='2026-09-01')
        self.assertEqual(progress_sep['spent'], Decimal('0.00'))
        self.assertEqual(progress_sep['percentage'], Decimal('0.00'))
        self.assertEqual(progress_sep['remaining'], Decimal('500.00'))
        self.assertFalse(progress_sep['is_warning'])

    def test_deposit_to_goal_success_and_validation(self):
        account = Account.objects.create(
            user=self.user,
            name='Investimentos',
            type=Account.Types.CHECKING,
            balance=Decimal('2000.00'),
            initial_balance=Decimal('2000.00')
        )
        goal = Goal.objects.create(
            user=self.user,
            account=account,
            name='Carro Novo',
            target_amount=Decimal('50000.00'),
            current_amount=Decimal('1000.00'),
            start_date='2026-08-01',
            end_date='2027-08-01'
        )
        
        # Successful deposit
        success = deposit_to_goal(goal, Decimal('500.00'))
        self.assertTrue(success)
        goal.refresh_from_db()
        self.assertEqual(goal.current_amount, Decimal('1500.00'))
        
        # Test invalid amount (<= 0)
        with self.assertRaises(ValueError):
            deposit_to_goal(goal, Decimal('-100.00'))

        with self.assertRaises(ValueError):
            deposit_to_goal(goal, Decimal('0.00'))

        # Test amount exceeding account free balance (free_balance is 2000 - 1500 = 500)
        with self.assertRaises(ValueError) as ctx:
            deposit_to_goal(goal, Decimal('600.00'))
        self.assertIn("Saldo livre insuficiente", str(ctx.exception))

    def test_create_budget_idor_prevention(self):
        other_user = User.objects.create_user(username='other_user', password='password123')
        other_category = Category.objects.create(
            user=other_user,
            name='Outro Gasto',
            type=TransactionType.EXPENSE
        )

        with self.assertRaises(ValidationError) as ctx:
            create_budget(
                user=self.user,
                category_id=str(other_category.id),
                amount=Decimal('500.00'),
                is_recurring=True
            )
        self.assertIn("Categoria inválida ou não encontrada", str(ctx.exception))

    def test_create_goal_other_user_account_prevention(self):
        other_user = User.objects.create_user(username='other_acc_user', password='password123')
        other_account = Account.objects.create(
            user=other_user,
            name='Conta Alheia',
            type=Account.Types.CHECKING,
            balance=Decimal('1000.00'),
            initial_balance=Decimal('1000.00')
        )

        with self.assertRaises(ValidationError) as ctx:
            create_goal(
                user=self.user,
                name='Objetivo Invasivo',
                target_amount=Decimal('1000.00'),
                current_amount=Decimal('0.00'),
                start_date='2026-08-01',
                end_date='2026-12-31',
                account=other_account
            )
        self.assertIn("Conta inválida para este usuário", str(ctx.exception))

    def test_delete_views_http_method_restriction(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('300.00'),
            is_recurring=True,
            start_date='2026-08-01'
        )
        goal = Goal.objects.create(
            user=self.user,
            name='Meta Teste',
            target_amount=Decimal('1000.00'),
            current_amount=Decimal('0.00'),
            start_date='2026-08-01',
            end_date='2026-12-31'
        )

        # GET on budget_delete must be blocked with 405
        res = self.client.get(f'/planning/budget/{budget.id}/delete/')
        self.assertEqual(res.status_code, 405)
        self.assertTrue(Budget.objects.filter(id=budget.id).exists())

        # GET on goal_delete must be blocked with 405
        res = self.client.get(f'/planning/goal/{goal.id}/delete/')
        self.assertEqual(res.status_code, 405)
        self.assertTrue(Goal.objects.filter(id=goal.id).exists())

    def test_account_deletion_sets_goal_account_to_null(self):
        account = Account.objects.create(
            user=self.user,
            name='Conta para Excluir',
            type=Account.Types.CHECKING,
            balance=Decimal('1000.00'),
            initial_balance=Decimal('1000.00')
        )
        goal = Goal.objects.create(
            user=self.user,
            account=account,
            name='Caixinha Salva',
            target_amount=Decimal('5000.00'),
            current_amount=Decimal('200.00'),
            start_date='2026-08-01',
            end_date='2026-12-31'
        )

        account.delete()
        goal.refresh_from_db()
        self.assertIsNone(goal.account)
        self.assertEqual(goal.name, 'Caixinha Salva')

    @patch('planning.tasks.send_push_notification')
    def test_notify_budget_warnings_and_monthly_reset(self, mock_push):
        from planning.tasks import notify_budget_warnings

        account = Account.objects.create(
            user=self.user,
            name='Conta Alerta',
            type=Account.Types.CHECKING,
            balance=Decimal('2000.00'),
            initial_balance=Decimal('2000.00')
        )
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('100.00'),
            is_recurring=True,
            start_date=date.today(),
            is_warning_notified=False
        )
        # Expense of 85 (85%)
        tx = Transaction.objects.create(
            user=self.user,
            account=account,
            category=self.category,
            description='Gasto 85%',
            amount=Decimal('85.00'),
            date=date.today(),
            status=Transaction.Statuses.COMPLETED
        )

        notify_budget_warnings()

        mock_push.assert_called_once()
        budget.refresh_from_db()
        self.assertTrue(budget.is_warning_notified)

        # Simulate month rollover (updated_at in the previous month)
        past_date = date.today().replace(day=1) - timedelta(days=5)
        Budget.objects.filter(id=budget.id).update(updated_at=past_date)

        # In the new month, past expenses do not count towards the new month
        tx.delete()

        # Running the task in the new month resets is_warning_notified
        notify_budget_warnings()
        budget.refresh_from_db()
        self.assertFalse(budget.is_warning_notified)

    def test_get_active_budgets_and_bulk_progress(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('500.00'),
            is_recurring=True,
            start_date=date(2026, 8, 1)
        )
        
        active_budgets = get_active_budgets(self.user, reference_date=date(2026, 8, 15))
        self.assertEqual(len(active_budgets), 1)
        self.assertEqual(active_budgets[0]['budget'].amount, Decimal('500.00'))

        budgets_with_progress = get_budgets_with_progress(self.user, reference_date=date(2026, 8, 15))
        self.assertEqual(len(budgets_with_progress), 1)
        self.assertEqual(budgets_with_progress[0].spent, Decimal('0.00'))
        self.assertEqual(budgets_with_progress[0].remaining, Decimal('500.00'))

    def test_budget_overlapping_validation(self):
        # Recurring budget
        Budget.objects.create(
            user=self.user, category=self.category, amount=Decimal('500.00'),
            is_recurring=True, start_date='2026-08-01'
        )
        
        # Creating another recurring budget for the same category must fail
        duplicate_budget = Budget(
            user=self.user, category=self.category, amount=Decimal('300.00'),
            is_recurring=True, start_date='2026-09-01'
        )
        with self.assertRaises(ValidationError):
            duplicate_budget.save()

