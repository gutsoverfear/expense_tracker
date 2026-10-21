from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Budget, Category, Expense, User
from app.schemas import BudgetResponse, BudgetUpsert

router = APIRouter(prefix="/budgets", tags=["budgets"])


def month_bounds(month: str) -> tuple[str, str]:
    year, month_number = (int(value) for value in month.split("-"))
    next_month = f"{year + (month_number == 12):04d}-{1 if month_number == 12 else month_number + 1:02d}"
    return month, next_month


@router.get("", response_model=list[BudgetResponse])
def list_budgets(month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BudgetResponse]:
    start, end = month_bounds(month)
    spent = select(Expense.category_id, func.sum(Expense.amount_paise).label("spent_paise")).where(Expense.user_id == current_user.id, Expense.date >= f"{start}-01", Expense.date < f"{end}-01").group_by(Expense.category_id).subquery()
    rows = db.execute(select(Budget, Category.name, func.coalesce(spent.c.spent_paise, 0)).join(Category, Category.id == Budget.category_id).outerjoin(spent, spent.c.category_id == Budget.category_id).where(Budget.user_id == current_user.id, Budget.month == month)).all()
    return [BudgetResponse(id=budget.id, category_id=budget.category_id, category_name=name, month=budget.month, limit_paise=budget.limit_paise, spent_paise=int(spent_amount), percentage=round(int(spent_amount) / budget.limit_paise * 100, 1)) for budget, name, spent_amount in rows]


@router.put("/{category_id}", response_model=BudgetResponse)
def upsert_budget(category_id: int, payload: BudgetUpsert, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BudgetResponse:
    category = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == current_user.id))
    if category is None or payload.category_id != category_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category")
    budget = db.scalar(select(Budget).where(Budget.user_id == current_user.id, Budget.category_id == category_id, Budget.month == payload.month))
    if budget is None:
        budget = Budget(user_id=current_user.id, category_id=category_id, month=payload.month, limit_paise=payload.limit_paise)
        db.add(budget)
    else:
        budget.limit_paise = payload.limit_paise
    db.commit()
    db.refresh(budget)
    row = db.execute(
        select(Budget, Category.name, func.coalesce(spent.c.spent_paise, 0))
        .join(Category, Category.id == Budget.category_id)
        .outerjoin(spent, spent.c.category_id == Budget.category_id)
        .where(Budget.id == budget.id, Budget.user_id == current_user.id)
    ).one()
    saved_budget, category_name, spent_amount = row
    spent_paise = int(spent_amount)
    return BudgetResponse(
        id=saved_budget.id,
        category_id=saved_budget.category_id,
        category_name=category_name,
        month=saved_budget.month,
        limit_paise=saved_budget.limit_paise,
        spent_paise=spent_paise,
        percentage=round(spent_paise / saved_budget.limit_paise * 100, 1),
    )