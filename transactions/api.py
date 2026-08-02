import uuid
from typing import List
from ninja import Router
from django.shortcuts import get_object_or_404

from transactions.schemas import CategoryIn, CategoryOut, TagIn, TagOut, TransactionOut, TransactionIn, TransferIn, TransferOut, RecurringTransactionIn, RecurringTransactionOut
from .models import Category, Tag, Transaction, RecurringTransaction, Transfer

router = Router(tags=["Categories"])

@router.post("/categories", response={201: CategoryOut})
def create_category(request, payload: CategoryIn):
    category = Category.objects.create(
        user=request.user,
        name=payload.name,
        type=payload.type,
        icon=payload.icon,
        color=payload.color,
        parent_id=payload.parent
    )
    return 201, category

@router.get("/categories/default", response=List[CategoryOut])
def list_default_categories(request):
    return Category.objects.filter(user__isnull=True).order_by('name')

@router.get("/categories", response=List[CategoryOut])
def list_categories(request):
    return Category.objects.filter(user=request.user).order_by('name')

@router.get("/categories/{category_id}", response=CategoryOut)
def get_category(request, category_id: uuid.UUID):
    category = get_object_or_404(Category, id=category_id, user=request.user)
    return category

@router.put("/categories/{category_id}", response=CategoryOut)
def update_category(request, category_id: uuid.UUID, payload: CategoryIn):
    category = get_object_or_404(Category, id=category_id, user=request.user)
    category.name = payload.name
    category.type = payload.type
    category.icon = payload.icon
    category.color = payload.color
    category.parent_id = payload.parent
    category.save()
    return category

@router.delete("/categories/{category_id}", response={204: None})
def delete_category(request, category_id: uuid.UUID):
    category = get_object_or_404(Category, id=category_id, user=request.user)
    category.delete()
    return 204, None

@router.post("/tags", response={201: TagOut})
def create_tag(request, payload: TagIn):
    tag = Tag.objects.create(
        user=request.user,
        name=payload.name,
        color=payload.color
    )
    return 201, tag

@router.get("/tags", response=List[TagOut])
def list_tags(request):
    return Tag.objects.filter(user=request.user).order_by('name')

@router.get("/tags/{tag_id}", response=TagOut)
def get_tag(request, tag_id: uuid.UUID):
    tag = get_object_or_404(Tag, id=tag_id, user=request.user)
    return tag

@router.put("/tags/{tag_id}", response=TagOut)
def update_tag(request, tag_id: uuid.UUID, payload: TagIn):
    tag = get_object_or_404(Tag, id=tag_id, user=request.user)
    tag.name = payload.name
    tag.color = payload.color
    tag.save()
    return tag

@router.delete("/tags/{tag_id}", response={204: None})
def delete_tag(request, tag_id: uuid.UUID):
    tag = get_object_or_404(Tag, id=tag_id, user=request.user)
    tag.delete()
    return 204, None

@router.post("/transactions", response={201: TransactionOut})
def create_transaction(request, payload: TransactionIn):
    transaction = Transaction.objects.create(
        user=request.user,
        account_id=payload.account,
        category_id=payload.category,
        description=payload.description,
        amount=payload.amount,
        date=payload.date,
        due_date=payload.due_date,
        status=payload.status,
        installment_number=payload.installment_number,
        total_installments=payload.total_installments,
        recurring=payload.recurring
    )
    if payload.tags:
        transaction.tags.set(payload.tags)
    return 201, transaction

@router.get("/transactions", response=List[TransactionOut])
def list_transactions(request):
    return Transaction.objects.filter(user=request.user).order_by("created_at")

@router.get("/transactions/{transaction_id}", response=TransactionOut)
def get_transaction(request, transaction_id: uuid.UUID):
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    return transaction

@router.put("/transactions/{transaction_id}", response=TransactionOut)
def update_transaction(request, transaction_id: uuid.UUID, payload: TransactionIn):
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    transaction.account_id = payload.account
    transaction.category_id = payload.category
    transaction.description = payload.description
    transaction.amount = payload.amount
    transaction.date = payload.date
    transaction.due_date = payload.due_date
    transaction.status = payload.status
    transaction.installment_number = payload.installment_number
    transaction.total_installments = payload.total_installments
    transaction.recurring = payload.recurring
    transaction.save()
    if payload.tags:
        transaction.tags.set(payload.tags)
    return transaction

@router.delete("/transactions/{transaction_id}", response={204: None})
def delete_transaction(request, transaction_id: uuid.UUID):
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    transaction.delete()
    return 204, None

@router.post("/recurring-transactions", response={201: RecurringTransactionOut})
def create_recurring_transaction(request, payload: RecurringTransactionIn):
    recurring_transaction = RecurringTransaction.objects.create(
            user=request.user,
            category_id=payload.category,
            account=payload.account,
            description=payload.description,
            amount=payload.amount,
            frequency=payload.frequency,
            start_date=payload.start_date,
            end_date=payload.end_date,
            active=payload.active
        )
    return 201, recurring_transaction

@router.get("/recurring-transactions", response=List[RecurringTransactionOut])
def list_recurring_transactions(request):
    return RecurringTransaction.objects.filter(user=request.user).order_by("created_at")

@router.get("/recurring-transactions/{transaction_id}", response=RecurringTransactionOut)
def get_recurring_transaction(request, transaction_id: uuid.UUID):
    recurring_transaction = get_object_or_404(RecurringTransaction, id=transaction_id, user=request.user)
    return recurring_transaction

@router.put("/recurring-transactions/{transaction_id}", response=RecurringTransactionOut)
def update_recurring_transaction(request, transaction_id: uuid.UUID, payload: RecurringTransactionIn):
    recurring_transaction = get_object_or_404(RecurringTransaction, id=transaction_id, user=request.user)
    recurring_transaction.category_id = payload.category
    recurring_transaction.account = payload.account
    recurring_transaction.description = payload.description
    recurring_transaction.amount = payload.amount
    recurring_transaction.frequency = payload.frequency
    recurring_transaction.start_date = payload.start_date
    recurring_transaction.end_date = payload.end_date
    recurring_transaction.active = payload.active
    recurring_transaction.save()
    return recurring_transaction

@router.delete("/recurring-transactions/{transaction_id}", response={204: None})
def delete_recurring_transaction(request, transaction_id: uuid.UUID):
    recurring_transaction = get_object_or_404(RecurringTransaction, id=transaction_id, user=request.user)
    recurring_transaction.delete()
    return 204, None

@router.post("/transfers", response={201: TransferOut})
def create_transfer(request, payload: TransferIn):
    out_transaction = Transaction.objects.create(
        user=request.user,
        account_id=payload.out_account_id,
        category=payload.category,
        description=payload.description,
        amount=payload.amount,
        date=payload.date,
        status=payload.status,
    )
    in_transaction = Transaction.objects.create(
        user=request.user,
        account_id=payload.in_account_id,
        category=payload.category,
        description=payload.description,
        amount=payload.amount,
        date=payload.date,
        status=payload.status,
    )
    transfer = Transfer.objects.create(
        user=request.user,
        out_transaction=out_transaction,
        in_transaction=in_transaction
    )
    if payload.recurring:
        out_transaction.recurring_id = payload.recurring
        in_transaction.recurring_id = payload.recurring
        out_transaction.save()
        in_transaction.save()
    return 201, transfer

@router.get("/transfers", response=List[TransferOut])
def list_transfers(request):
    return Transfer.objects.filter(user=request.user).order_by("created_at")

@router.get("/transfers/{transfer_id}", response=TransferOut)
def get_transfer(request, transfer_id: uuid.UUID):
    transfer = get_object_or_404(Transfer, id=transfer_id, user=request.user)
    return transfer

@router.put("/transfers/{transfer_id}", response=TransferOut)
def update_transfer(request, transfer_id: uuid.UUID, payload: TransferIn):
    transfer = get_object_or_404(Transfer, id=transfer_id, user=request.user)
    transfer.out_transaction.account_id = payload.out_account_id
    transfer.in_transaction.account_id = payload.in_account_id
    transfer.out_transaction.category = payload.category
    transfer.in_transaction.category = payload.category
    transfer.out_transaction.description = payload.description
    transfer.in_transaction.description = payload.description
    transfer.out_transaction.amount = payload.amount
    transfer.in_transaction.amount = payload.amount
    transfer.out_transaction.date = payload.date
    transfer.in_transaction.date = payload.date
    transfer.out_transaction.status = payload.status
    transfer.in_transaction.status = payload.status
    if payload.recurring:
        transfer.out_transaction.recurring_id = payload.recurring
        transfer.in_transaction.recurring_id = payload.recurring
    else:
        transfer.out_transaction.recurring_id = None
        transfer.in_transaction.recurring_id = None

    transfer.out_transaction.save()
    transfer.in_transaction.save()
    return transfer

@router.delete("/transfers/{transfer_id}", response={204: None})
def delete_transfer(request, transfer_id: uuid.UUID):
    transfer = get_object_or_404(Transfer, id=transfer_id, user=request.user)
    transfer.out_transaction.delete()
    transfer.in_transaction.delete()
    transfer.delete()
    return 204, None