from decimal import Decimal

from django.core.management.base import BaseCommand

from wallets.models import Account
from wallets.services import recalculate_account_balance


class Command(BaseCommand):
    help = 'Verifies and optionally reconciles stored account balances against recorded transactions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically fix and recalculate any inconsistent balances in the database.',
        )

    def handle(self, *args, **options):
        fix = options['fix']
        accounts = Account.objects.select_related('user').all()
        discrepancies = 0

        self.stdout.write(self.style.NOTICE(f"Checking balance integrity for {accounts.count()} accounts..."))

        for account in accounts:
            current_balance = account.balance
            # Calculate what the balance should be without saving
            from moneta.common import TransactionType
            from transactions.models import Transaction, Transfer

            status_filter = [Transaction.Statuses.COMPLETED]
            if account.type == Account.Types.CREDIT_CARD:
                status_filter.append(Transaction.Statuses.PENDING)

            completed_txs = Transaction.objects.filter(
                account=account,
                status__in=status_filter,
            ).exclude(category__type=TransactionType.TRANSFER)

            from django.db import models
            incomes = completed_txs.filter(category__type=TransactionType.INCOME).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            expenses = completed_txs.filter(category__type=TransactionType.EXPENSE).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

            transfers_out = Transfer.objects.filter(
                out_transaction__account=account,
                out_transaction__status__in=status_filter,
            ).aggregate(total=models.Sum('out_transaction__amount'))['total'] or Decimal('0.00')

            transfers_in = Transfer.objects.filter(
                in_transaction__account=account,
                in_transaction__status__in=status_filter,
            ).aggregate(total=models.Sum('in_transaction__amount'))['total'] or Decimal('0.00')

            expected_balance = account.initial_balance + incomes - expenses - transfers_out + transfers_in
            expected_balance = Decimal(expected_balance).quantize(Decimal('.01'))

            if current_balance != expected_balance:
                discrepancies += 1
                diff = expected_balance - current_balance
                if fix:
                    recalculate_account_balance(account)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[FIXED] Account '{account.name}' (User: {account.user.username}): "
                            f"Stored R$ {current_balance} -> Reconciled to R$ {expected_balance} (Diff: R$ {diff})"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[MISMATCH] Account '{account.name}' (User: {account.user.username}): "
                            f"Stored R$ {current_balance} vs Calculated R$ {expected_balance} (Diff: R$ {diff})"
                        )
                    )

        if discrepancies == 0:
            self.stdout.write(self.style.SUCCESS("All account balances are consistent with recorded transactions."))
        elif not fix:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {discrepancies} account(s) with balance discrepancies. Run with --fix to reconcile."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully reconciled {discrepancies} account(s).")
            )
