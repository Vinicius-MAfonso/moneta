from django.db import models

class Category(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=[('income', 'Income'), ('expense', 'Expense')])
    icon = models.CharField(max_length=100, blank=True, null=True)
    color = models.CharField(max_length=7, default='#000000')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='subcategories')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class Tag(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#000000')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Transaction(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    account = models.ForeignKey('wallets.Account', on_delete=models.CASCADE)
    credit_card = models.ForeignKey('wallets.CreditCard', on_delete=models.CASCADE)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=[('income', 'Income'), ('expense', 'Expense')])
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    due_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('completed', 'Completed')], default='pending')
    installment_number = models.PositiveIntegerField(blank=True, null=True)
    total_installments = models.PositiveIntegerField(blank=True, null=True)
    recurring = models.ForeignKey('RecurringTransaction', on_delete=models.CASCADE, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} - {self.amount} ({self.type})"

class Transfer(models.Model):
    from_account = models.ForeignKey('wallets.Account', on_delete=models.CASCADE, related_name='transfers_out')
    to_account = models.ForeignKey('wallets.Account', on_delete=models.CASCADE, related_name='transfers_in')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Transfer from {self.from_account} to {self.to_account} - {self.amount}"

class RecurringTransaction(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    account = models.ForeignKey('wallets.Account', on_delete=models.CASCADE)
    credit_card = models.ForeignKey('wallets.CreditCard', on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=10, choices=[('income', 'Income'),('expense', 'Expense')])
    frequency = models.CharField(max_length=10, choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('yearly', 'Yearly')])
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.description} - {self.amount} ({self.type})"

class TransactionTag(models.Model):
    transaction = models.ForeignKey('Transaction', on_delete=models.CASCADE)
    tag = models.ForeignKey('Tag', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('transaction', 'tag')

    def __str__(self):
        return f"{self.transaction} - {self.tag}"