from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Category, PaymentMethod, RecurringExpense, User
from app.schemas import RecurringExpenseCreate, RecurringExpenseResponse, RecurringExpenseUpdate

router = APIRouter(prefix="/recurring-expenses", tags=["recurring expenses"])


def owned_recurring(item_id: int, user_id: int, db: Session) -> RecurringExpense:
    item = db.scalar(select(RecurringExpense).where(RecurringExpense.id == item_id, RecurringExpense.user_id == user_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring expense not found")
    return item


def validate_references(category_id: int | None, payment_method_id: int | None, user_id: int, db: Session) -> None:
    if category_id is not None and db.scalar(select(Category.id).where(Category.id == category_id, Category.user_id == user_id)) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category")
    if payment_method_id is not None and db.scalar(select(PaymentMethod.id).where(PaymentMethod.id == payment_method_id, PaymentMethod.user_id == user_id)) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment method")


@router.get("", response_model=list[RecurringExpenseResponse])
def list_recurring(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[RecurringExpense]:
    return list(db.scalars(select(RecurringExpense).where(RecurringExpense.user_id == current_user.id).order_by(RecurringExpense.active.desc(), RecurringExpense.next_run_date)))


@router.post("", response_model=RecurringExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_recurring(payload: RecurringExpenseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RecurringExpense:
    validate_references(payload.category_id, payload.payment_method_id, current_user.id, db)
    item = RecurringExpense(user_id=current_user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{item_id}", response_model=RecurringExpenseResponse)
def update_recurring(item_id: int, payload: RecurringExpenseUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RecurringExpense:
    item = owned_recurring(item_id, current_user.id, db)
    values = payload.model_dump(exclude_unset=True)
    validate_references(values.get("category_id", item.category_id), values.get("payment_method_id", item.payment_method_id), current_user.id, db)
    for field, value in values.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    item = owned_recurring(item_id, current_user.id, db)
    db.delete(item)
    db.commit()