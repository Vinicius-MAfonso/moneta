import uuid
from typing import List
from ninja import Router
from django.shortcuts import get_object_or_404

from .models import Account, CreditCardDetails
from .schemas import AccountIn, AccountOut, CreditCardDetailsIn, CreditCardDetailsOut

router = Router(tags=["Wallets"])


@router.post("/accounts", response={201: AccountOut})
def create_account(request, payload: AccountIn):
    account = Account.objects.create(
        user=request.user,
        name=payload.name,
        type=payload.type,
        institution=payload.institution,
        balance=payload.balance,
        color=payload.color,
        active=payload.active,
    )
    return 201, account


@router.get("/accounts", response=List[AccountOut])
def list_accounts(request):
    return Account.objects.filter(user=request.user)


@router.get("/accounts/{account_id}", response=AccountOut)
def get_account(request, account_id: uuid.UUID):
    account = get_object_or_404(Account, id=account_id, user=request.user)
    return account


@router.put("/accounts/{account_id}", response=AccountOut)
def update_account(request, account_id: uuid.UUID, payload: AccountIn):
    account = get_object_or_404(Account, id=account_id, user=request.user)
    account.name = payload.name
    account.type = payload.type
    account.institution = payload.institution
    account.balance = payload.balance
    account.color = payload.color
    account.active = payload.active
    account.save()
    return account


@router.delete("/accounts/{account_id}", response={204: None})
def delete_account(request, account_id: uuid.UUID):
    account = get_object_or_404(Account, id=account_id, user=request.user)
    account.delete()
    return 204, None


@router.post("/accounts/{account_id}/credit-card", response={201: CreditCardDetailsOut})
def create_or_update_credit_card_details(request, account_id: uuid.UUID, payload: CreditCardDetailsIn):
    account = get_object_or_404(Account, id=account_id, user=request.user)
    details, created = CreditCardDetails.objects.update_or_create(
        account=account,
        defaults={
            'limit': payload.limit,
            'available_limit': payload.available_limit,
            'closing_day': payload.closing_day,
            'due_day': payload.due_day,
        }
    )
    status_code = 201 if created else 200
    return status_code, details


@router.get("/accounts/{account_id}/credit-card", response=CreditCardDetailsOut)
def get_credit_card_details(request, account_id: uuid.UUID):
    account = get_object_or_404(Account, id=account_id, user=request.user)
    details = get_object_or_404(CreditCardDetails, account=account)
    return details


@router.delete("/accounts/{account_id}/credit-card", response={204: None})
def delete_credit_card_details(request, account_id: uuid.UUID):
    account = get_object_or_404(Account, id=account_id, user=request.user)
    details = get_object_or_404(CreditCardDetails, account=account)
    details.delete()
    return 204, None
