import uuid
from decimal import Decimal
from ninja import Schema


class InvestmentIn(Schema):
    account: uuid.UUID
    name: str
    type: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal


class InvestmentOut(Schema):
    id: uuid.UUID
    account_id: uuid.UUID
    name: str
    type: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal
