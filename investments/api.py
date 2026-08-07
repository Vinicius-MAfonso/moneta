import uuid
from typing import List
from ninja import Router
from django.shortcuts import get_object_or_404

from .models import Investment
from .schemas import InvestmentIn, InvestmentOut

router = Router(tags=["Investments"])


@router.post("/investments", response={201: InvestmentOut})
def create_investment(request, payload: InvestmentIn):
    investment = Investment.objects.create(
        user=request.user,
        account_id=payload.account,
        name=payload.name,
        type=payload.type,
        quantity=payload.quantity,
        average_price=payload.average_price,
        current_price=payload.current_price,
    )
    return 201, investment


@router.get("/investments", response=List[InvestmentOut])
def list_investments(request):
    return Investment.objects.filter(user=request.user)


@router.get("/investments/{investment_id}", response=InvestmentOut)
def get_investment(request, investment_id: uuid.UUID):
    investment = get_object_or_404(Investment, id=investment_id, user=request.user)
    return investment


@router.put("/investments/{investment_id}", response=InvestmentOut)
def update_investment(request, investment_id: uuid.UUID, payload: InvestmentIn):
    investment = get_object_or_404(Investment, id=investment_id, user=request.user)
    investment.account_id = payload.account
    investment.name = payload.name
    investment.type = payload.type
    investment.quantity = payload.quantity
    investment.average_price = payload.average_price
    investment.current_price = payload.current_price
    investment.save()
    return investment


@router.delete("/investments/{investment_id}", response={204: None})
def delete_investment(request, investment_id: uuid.UUID):
    investment = get_object_or_404(Investment, id=investment_id, user=request.user)
    investment.delete()
    return 204, None
