from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import PaymentMethod, User
from app.schemas import PaymentMethodCreate, PaymentMethodResponse, PaymentMethodUpdate

router = APIRouter(prefix="/payment-methods", tags=["payment methods"])


def get_owned_payment_method(payment_method_id: int, user_id: int, db: Session) -> PaymentMethod:
    payment_method = db.scalar(
        select(PaymentMethod).where(
            PaymentMethod.id == payment_method_id, PaymentMethod.user_id == user_id
        )
    )
    if payment_method is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found"
        )
    return payment_method


@router.get("", response_model=list[PaymentMethodResponse])
def list_payment_methods(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[PaymentMethod]:
    return list(
        db.scalars(
            select(PaymentMethod)
            .where(PaymentMethod.user_id == current_user.id)
            .order_by(PaymentMethod.id)
        )
    )


@router.post("", response_model=PaymentMethodResponse, status_code=status.HTTP_201_CREATED)
def create_payment_method(
    payload: PaymentMethodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentMethod:
    payment_method = PaymentMethod(user_id=current_user.id, **payload.model_dump())
    db.add(payment_method)
    db.commit()
    db.refresh(payment_method)
    return payment_method


@router.get("/{payment_method_id}", response_model=PaymentMethodResponse)
def read_payment_method(
    payment_method_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentMethod:
    return get_owned_payment_method(payment_method_id, current_user.id, db)


@router.put("/{payment_method_id}", response_model=PaymentMethodResponse)
def update_payment_method(
    payment_method_id: int,
    payload: PaymentMethodUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentMethod:
    payment_method = get_owned_payment_method(payment_method_id, current_user.id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(payment_method, field, value)
    db.commit()
    db.refresh(payment_method)
    return payment_method


@router.delete("/{payment_method_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment_method(
    payment_method_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    payment_method = get_owned_payment_method(payment_method_id, current_user.id, db)
    db.delete(payment_method)
    db.commit()