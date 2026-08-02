import uuid
from datetime import date
from ninja import Schema


class CategoryIn(Schema):
    name: str
    type: str
    icon: str | None = None
    color: str
    parent: uuid.UUID | None = None

class CategoryOut(Schema):
    id: uuid.UUID
    name: str
    type: str
    icon: str | None = None
    color: str

class TagIn(Schema):
    name: str
    color: str

class TagOut(Schema):
    id: uuid.UUID
    name: str
    color: str

class TransactionIn(Schema):
    account: uuid.UUID
    category: uuid.UUID
    tags: list[uuid.UUID] | None = None
    description: str
    amount: float
    date: date
    due_date: date | None = None
    status: str
    installment_number: int | None = None
    total_installments: int | None = None
    recurring: uuid.UUID | None = None

class RecurringTransactionIn(Schema):
    category: uuid.UUID
    account: uuid.UUID
    description: str
    amount: float
    frequency: str
    start_date: date
    end_date: date | None = None
    active: bool | None = True

class RecurringTransactionOut(Schema):
    id: uuid.UUID
    category: uuid.UUID
    account: uuid.UUID
    description: str
    amount: float
    frequency: str
    start_date: date
    end_date: date | None = None
    active: bool | None = True

class TransactionOut(Schema):
    id: uuid.UUID
    account: uuid.UUID
    category: uuid.UUID
    tags: list[uuid.UUID] | None = None
    description: str
    amount: float
    date: date
    due_date: date | None = None
    status: str
    installment_number: int | None = None
    total_installments: int | None = None
    recurring: uuid.UUID | None = None

class TransferIn(Schema):
    out_account_id: uuid.UUID
    in_account_id: uuid.UUID
    category: uuid.UUID | None = None
    description: str
    amount: float
    date: date
    status: str
    recurring: uuid.UUID | None = None

class TransferOut(Schema):
    id: uuid.UUID
    out_transaction: TransactionOut
    in_transaction: TransactionOut
