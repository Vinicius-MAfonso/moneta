import uuid
from decimal import Decimal
from ninja import Schema


class AccountIn(Schema):
    name: str
    type: str
    institution: str | None = None
    balance: Decimal = Decimal('0.00')
    color: str = '#000000'
    active: bool = True


class AccountOut(Schema):
    id: uuid.UUID
    name: str
    type: str
    institution: str | None = None
    balance: Decimal
    color: str
    active: bool


class CreditCardDetailsIn(Schema):
    limit: Decimal = Decimal('0.00')
    available_limit: Decimal = Decimal('0.00')
    closing_day: int
    due_day: int


class CreditCardDetailsOut(Schema):
    account_id: uuid.UUID
    limit: Decimal
    available_limit: Decimal
    closing_day: int
    due_day: int
