import csv
import io
import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Category, Expense, PaymentMethod, User
from app.schemas import (
    DailySpending,
    ExpenseCreate,
    ExpenseImportCommit,
    ExpenseResponse,
    ExpenseSummaryResponse,
    ExpenseUpdate,
    SpendingBreakdown,
    SpendingTotal,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])

CSV_FIELDS = ("amount_paise", "date", "category", "payment_method", "note")


def get_owned_expense(expense_id: int, user_id: int, db: Session) -> Expense:
    expense = db.scalar(select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id))
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    return expense


def validate_reference_ids(
    category_id: int | None, payment_method_id: int | None, user_id: int, db: Session
) -> None:
    if category_id is not None and db.scalar(
        select(Category.id).where(Category.id == category_id, Category.user_id == user_id)
    ) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category")
    if payment_method_id is not None and db.scalar(
        select(PaymentMethod.id).where(
            PaymentMethod.id == payment_method_id, PaymentMethod.user_id == user_id
        )
    ) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment method"
        )


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Expense:
    validate_reference_ids(payload.category_id, payload.payment_method_id, current_user.id, db)
    expense = Expense(user_id=current_user.id, **payload.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("", response_model=list[ExpenseResponse])
def list_expenses(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    category_id: int | None = Query(default=None, ge=1),
    payment_method_id: int | None = Query(default=None, ge=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Expense]:
    query = select(Expense).where(Expense.user_id == current_user.id)
    if start_date is not None:
        query = query.where(Expense.date >= start_date)
    if end_date is not None:
        query = query.where(Expense.date <= end_date)
    if category_id is not None:
        query = query.where(Expense.category_id == category_id)
    if payment_method_id is not None:
        query = query.where(Expense.payment_method_id == payment_method_id)
    return list(
        db.scalars(query.order_by(Expense.date.desc(), Expense.id.desc()).offset(skip).limit(limit))
    )


@router.get("/export")
def export_expenses(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    expenses = list(
        db.scalars(
            select(Expense)
            .where(Expense.user_id == current_user.id)
            .order_by(Expense.date.desc(), Expense.id.desc())
        )
    )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for expense in expenses:
        writer.writerow({
            "amount_paise": expense.amount_paise,
            "date": expense.date.isoformat(),
            "category": expense.category.name if expense.category else "",
            "payment_method": expense.payment_method.name if expense.payment_method else "",
            "note": expense.note or "",
        })
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


@router.post("/import/preview")
async def preview_import(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    try:
        mapping_data = json.loads(mapping)
        if not isinstance(mapping_data, dict) or any(field not in CSV_FIELDS for field in mapping_data):
            raise ValueError
        content = (await file.read()).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            raise ValueError
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid CSV or column mapping") from None

    category_names = {name.lower() for name in db.scalars(select(Category.name).where(Category.user_id == current_user.id))}
    method_names = {name.lower() for name in db.scalars(select(PaymentMethod.name).where(PaymentMethod.user_id == current_user.id))}
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    for index, source_row in enumerate(reader, start=2):
        row: dict[str, object] = {}
        try:
            row["amount_paise"] = int(str(source_row.get(mapping_data.get("amount_paise", ""), "")).strip())
            row["date"] = date.fromisoformat(str(source_row.get(mapping_data.get("date", ""), "")).strip()).isoformat()
            row["category"] = str(source_row.get(mapping_data.get("category", ""), "")).strip() or None
            row["payment_method"] = str(source_row.get(mapping_data.get("payment_method", ""), "")).strip() or None
            row["note"] = str(source_row.get(mapping_data.get("note", ""), "")).strip() or None
            if row["amount_paise"] <= 0:
                raise ValueError
            if row["category"] and str(row["category"]).lower() not in category_names:
                errors.append(f"Row {index}: unknown category")
            if row["payment_method"] and str(row["payment_method"]).lower() not in method_names:
                errors.append(f"Row {index}: unknown payment method")
            rows.append(row)
        except (TypeError, ValueError):
            errors.append(f"Row {index}: amount_paise must be positive and date must be YYYY-MM-DD")
    return {"columns": reader.fieldnames, "rows": rows[:100], "total_rows": len(rows), "errors": errors[:100]}


@router.post("/import")
def commit_import(
    payload: ExpenseImportCommit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    categories = {name.lower(): category.id for category, name in db.execute(select(Category, Category.name).where(Category.user_id == current_user.id))}
    methods = {name.lower(): method.id for method, name in db.execute(select(PaymentMethod, PaymentMethod.name).where(PaymentMethod.user_id == current_user.id))}
    expenses: list[Expense] = []
    for row in payload.rows:
        category_id = categories.get(row.category.lower()) if row.category else None
        payment_method_id = methods.get(row.payment_method.lower()) if row.payment_method else None
        if row.category and category_id is None:
            raise HTTPException(status_code=400, detail=f"Unknown category: {row.category}")
        if row.payment_method and payment_method_id is None:
            raise HTTPException(status_code=400, detail=f"Unknown payment method: {row.payment_method}")
        expenses.append(Expense(user_id=current_user.id, amount_paise=row.amount_paise, date=row.date, category_id=category_id, payment_method_id=payment_method_id, note=row.note))
    db.add_all(expenses)
    db.commit()
    return {"imported": len(expenses)}


@router.get("/summary", response_model=ExpenseSummaryResponse)
def spending_summary(
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpenseSummaryResponse:
    year, month_number = (int(value) for value in month.split("-"))
    start_date = date(year, month_number, 1)
    end_date = date(year + (month_number == 12), 1 if month_number == 12 else month_number + 1, 1)
    month_filter = (Expense.user_id == current_user.id, Expense.date >= start_date, Expense.date < end_date)

    total = db.scalar(select(func.coalesce(func.sum(Expense.amount_paise), 0)).where(*month_filter))
    category_name = func.coalesce(Category.name, literal("Uncategorized"))
    category_rows = db.execute(
        select(category_name.label("label"), func.sum(Expense.amount_paise).label("amount_paise"))
        .select_from(Expense)
        .outerjoin(Category, Category.id == Expense.category_id)
        .where(*month_filter)
        .group_by(category_name)
        .order_by(func.sum(Expense.amount_paise).desc())
    ).all()
    method_name = func.coalesce(PaymentMethod.name, literal("No payment method"))
    method_rows = db.execute(
        select(method_name.label("label"), func.sum(Expense.amount_paise).label("amount_paise"))
        .select_from(Expense)
        .outerjoin(PaymentMethod, PaymentMethod.id == Expense.payment_method_id)
        .where(*month_filter)
        .group_by(method_name)
        .order_by(func.sum(Expense.amount_paise).desc())
    ).all()
    daily_rows = db.execute(
        select(Expense.date, func.sum(Expense.amount_paise).label("amount_paise"))
        .where(*month_filter)
        .group_by(Expense.date)
        .order_by(Expense.date)
    ).all()
    top_expenses = list(
        db.scalars(
            select(Expense)
            .where(*month_filter)
            .order_by(Expense.amount_paise.desc(), Expense.id.desc())
            .limit(5)
        )
    )
    return ExpenseSummaryResponse(
        month=month,
        total=SpendingTotal(amount_paise=int(total or 0)),
        by_category=[SpendingBreakdown(label=row.label, amount_paise=int(row.amount_paise)) for row in category_rows],
        by_payment_method=[SpendingBreakdown(label=row.label, amount_paise=int(row.amount_paise)) for row in method_rows],
        daily=[DailySpending(date=row.date, amount_paise=int(row.amount_paise)) for row in daily_rows],
        top_expenses=top_expenses,
    )


@router.get("/{expense_id}", response_model=ExpenseResponse)
def read_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Expense:
    return get_owned_expense(expense_id, current_user.id, db)


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Expense:
    expense = get_owned_expense(expense_id, current_user.id, db)
    values = payload.model_dump(exclude_unset=True)
    validate_reference_ids(
        values.get("category_id", expense.category_id),
        values.get("payment_method_id", expense.payment_method_id),
        current_user.id,
        db,
    )
    for field, value in values.items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    expense = get_owned_expense(expense_id, current_user.id, db)
    db.delete(expense)
    db.commit()