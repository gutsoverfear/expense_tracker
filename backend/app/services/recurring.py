from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expense, RecurringExpense


def next_date(run_date: date, frequency: str) -> date:
    if frequency == "daily":
        return run_date + timedelta(days=1)
    if frequency == "weekly":
        return run_date + timedelta(days=7)
    month = run_date.month % 12 + 1
    year = run_date.year + (run_date.month == 12)
    day = min(run_date.day, 28)
    return date(year, month, day)


def generate_due_recurring_expenses(db: Session, run_date: date | None = None) -> int:
    current_date = run_date or date.today()
    recurring_items = list(
        db.scalars(
            select(RecurringExpense).where(
                RecurringExpense.active,
                RecurringExpense.next_run_date <= current_date,
            )
        )
    )
    generated = 0
    for recurring in recurring_items:
        while recurring.next_run_date <= current_date:
            exists = db.scalar(
                select(Expense.id).where(
                    Expense.recurring_expense_id == recurring.id,
                    Expense.date == recurring.next_run_date,
                )
            )
            if exists is None:
                db.add(Expense(user_id=recurring.user_id, amount_paise=recurring.amount_paise, date=recurring.next_run_date, category_id=recurring.category_id, payment_method_id=recurring.payment_method_id, note=recurring.note, recurring_expense_id=recurring.id))
                generated += 1
            recurring.next_run_date = next_date(recurring.next_run_date, recurring.frequency)
    db.commit()
    return generated