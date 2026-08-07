import uuid
from datetime import date
from decimal import Decimal
from ninja import Schema


class BudgetIn(Schema):
    category: uuid.UUID
    amount: Decimal
    start_date: date
    end_date: date


class BudgetOut(Schema):
    id: uuid.UUID
    category_id: uuid.UUID
    amount: Decimal
    start_date: date
    end_date: date


class GoalIn(Schema):
    name: str
    target_amount: Decimal
    current_amount: Decimal = Decimal('0.00')
    start_date: date
    end_date: date


class GoalOut(Schema):
    id: uuid.UUID
    name: str
    target_amount: Decimal
    current_amount: Decimal
    start_date: date
    end_date: date


class GoalTransactionIn(Schema):
    goal: uuid.UUID
    transaction: uuid.UUID
    amount: Decimal


class GoalTransactionOut(Schema):
    id: uuid.UUID
    goal_id: uuid.UUID
    transaction_id: uuid.UUID
    amount: Decimal
