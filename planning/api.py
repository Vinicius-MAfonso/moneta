import uuid
from typing import List
from ninja import Router
from django.shortcuts import get_object_or_404

from .models import Budget, Goal, GoalTransaction
from .schemas import (
    BudgetIn, BudgetOut,
    GoalIn, GoalOut,
    GoalTransactionIn, GoalTransactionOut,
)

router = Router(tags=["Planning"])


# Budgets
@router.post("/budgets", response={201: BudgetOut})
def create_budget(request, payload: BudgetIn):
    budget = Budget.objects.create(
        user=request.user,
        category_id=payload.category,
        amount=payload.amount,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return 201, budget


@router.get("/budgets", response=List[BudgetOut])
def list_budgets(request):
    return Budget.objects.filter(user=request.user)


@router.get("/budgets/{budget_id}", response=BudgetOut)
def get_budget(request, budget_id: uuid.UUID):
    budget = get_object_or_404(Budget, id=budget_id, user=request.user)
    return budget


@router.put("/budgets/{budget_id}", response=BudgetOut)
def update_budget(request, budget_id: uuid.UUID, payload: BudgetIn):
    budget = get_object_or_404(Budget, id=budget_id, user=request.user)
    budget.category_id = payload.category
    budget.amount = payload.amount
    budget.start_date = payload.start_date
    budget.end_date = payload.end_date
    budget.save()
    return budget


@router.delete("/budgets/{budget_id}", response={204: None})
def delete_budget(request, budget_id: uuid.UUID):
    budget = get_object_or_404(Budget, id=budget_id, user=request.user)
    budget.delete()
    return 204, None


# Goals
@router.post("/goals", response={201: GoalOut})
def create_goal(request, payload: GoalIn):
    goal = Goal.objects.create(
        user=request.user,
        name=payload.name,
        target_amount=payload.target_amount,
        current_amount=payload.current_amount,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return 201, goal


@router.get("/goals", response=List[GoalOut])
def list_goals(request):
    return Goal.objects.filter(user=request.user)


@router.get("/goals/{goal_id}", response=GoalOut)
def get_goal(request, goal_id: uuid.UUID):
    goal = get_object_or_404(Goal, id=goal_id, user=request.user)
    return goal


@router.put("/goals/{goal_id}", response=GoalOut)
def update_goal(request, goal_id: uuid.UUID, payload: GoalIn):
    goal = get_object_or_404(Goal, id=goal_id, user=request.user)
    goal.name = payload.name
    goal.target_amount = payload.target_amount
    goal.current_amount = payload.current_amount
    goal.start_date = payload.start_date
    goal.end_date = payload.end_date
    goal.save()
    return goal


@router.delete("/goals/{goal_id}", response={204: None})
def delete_goal(request, goal_id: uuid.UUID):
    goal = get_object_or_404(Goal, id=goal_id, user=request.user)
    goal.delete()
    return 204, None


# Goal Transactions
@router.post("/goal-transactions", response={201: GoalTransactionOut})
def create_goal_transaction(request, payload: GoalTransactionIn):
    goal = get_object_or_404(Goal, id=payload.goal, user=request.user)
    link = GoalTransaction.objects.create(
        goal=goal,
        transaction_id=payload.transaction,
        amount=payload.amount,
    )
    return 201, link


@router.get("/goal-transactions", response=List[GoalTransactionOut])
def list_goal_transactions(request):
    return GoalTransaction.objects.filter(goal__user=request.user)


@router.get("/goal-transactions/{link_id}", response=GoalTransactionOut)
def get_goal_transaction(request, link_id: uuid.UUID):
    link = get_object_or_404(GoalTransaction, id=link_id, goal__user=request.user)
    return link


@router.delete("/goal-transactions/{link_id}", response={204: None})
def delete_goal_transaction(request, link_id: uuid.UUID):
    link = get_object_or_404(GoalTransaction, id=link_id, goal__user=request.user)
    link.delete()
    return 204, None
