from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove the DB-level CHECK constraint on account balance.
    The Python-level validation in Account.clean() still protects normal forms.
    This allows OFX imports and other admin operations to work with historically
    negative balances that occur when importing past transaction data.
    """

    dependencies = [
        ('wallets', '0007_account_prevent_negative_balance_on_checking_accounts'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='account',
            name='prevent_negative_balance_on_checking_accounts',
        ),
    ]
