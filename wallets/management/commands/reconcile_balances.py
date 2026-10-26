from django.core.management.base import BaseCommand

from wallets.models import Account
from wallets.services import compute_account_balance, recalculate_account_balance


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
            expected_balance = compute_account_balance(account)

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
