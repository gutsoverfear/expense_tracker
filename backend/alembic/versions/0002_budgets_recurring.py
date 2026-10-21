"""Add category budgets and recurring expenses.

Revision ID: 0002_budgets_recurring
Revises: 0001_initial
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_budgets_recurring"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("recurring_expenses",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False), sa.Column("category_id", sa.Integer()),
        sa.Column("payment_method_id", sa.Integer()), sa.Column("note", sa.Text()),
        sa.Column("frequency", sa.String(length=10), nullable=False), sa.Column("next_run_date", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_method_id"], ["payment_methods.id"], ondelete="SET NULL"))
    op.create_index("ix_recurring_expenses_user_id", "recurring_expenses", ["user_id"])
    op.create_table("budgets",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False), sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("limit_paise", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "category_id", "month", name="uq_budget_user_category_month"))
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])
    op.create_index("ix_budgets_month", "budgets", ["month"])
    op.add_column("expenses", sa.Column("recurring_expense_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_expenses_recurring_expense_id", "expenses", "recurring_expenses", ["recurring_expense_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_expenses_recurring_expense_id", "expenses", type_="foreignkey")
    op.drop_column("expenses", "recurring_expense_id")
    op.drop_index("ix_budgets_month", table_name="budgets")
    op.drop_index("ix_budgets_user_id", table_name="budgets")
    op.drop_table("budgets")
    op.drop_index("ix_recurring_expenses_user_id", table_name="recurring_expenses")
    op.drop_table("recurring_expenses")