from datetime import date, date as date_type, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=100)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=100)


class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PaymentMethodBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PaymentMethodCreate(PaymentMethodBase):
    pass


class PaymentMethodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class PaymentMethodResponse(PaymentMethodBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ExpenseBase(BaseModel):
    amount_paise: int = Field(ge=0)
    date: date_type
    category_id: int | None = Field(default=None, ge=1)
    payment_method_id: int | None = Field(default=None, ge=1)
    note: str | None = None


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    amount_paise: int | None = Field(default=None, ge=0)
    date: date_type | None = None
    category_id: int | None = Field(default=None, ge=1)
    payment_method_id: int | None = Field(default=None, ge=1)
    note: str | None = None


class ExpenseResponse(ExpenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class BudgetUpsert(BaseModel):
    category_id: int = Field(ge=1)
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    limit_paise: int = Field(gt=0)


class BudgetResponse(BaseModel):
    id: int
    category_id: int
    category_name: str
    month: str
    limit_paise: int
    spent_paise: int
    percentage: float


class RecurringExpenseCreate(BaseModel):
    amount_paise: int = Field(gt=0)
    category_id: int | None = Field(default=None, ge=1)
    payment_method_id: int | None = Field(default=None, ge=1)
    note: str | None = None
    frequency: str = Field(pattern="^(daily|weekly|monthly)$")
    next_run_date: date_type


class RecurringExpenseUpdate(BaseModel):
    amount_paise: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, ge=1)
    payment_method_id: int | None = Field(default=None, ge=1)
    note: str | None = None
    frequency: str | None = Field(default=None, pattern="^(daily|weekly|monthly)$")
    next_run_date: date_type | None = None
    active: bool | None = None


class RecurringExpenseResponse(RecurringExpenseCreate):
    id: int
    active: bool
    created_at: datetime


class SpendingTotal(BaseModel):
    amount_paise: int


class SpendingBreakdown(BaseModel):
    label: str
    amount_paise: int


class DailySpending(BaseModel):
    date: date
    amount_paise: int


class ExpenseSummaryResponse(BaseModel):
    month: str
    total: SpendingTotal
    by_category: list[SpendingBreakdown]
    by_payment_method: list[SpendingBreakdown]
    daily: list[DailySpending]
    top_expenses: list[ExpenseResponse]


class ExpenseImportRow(BaseModel):
    amount_paise: int = Field(gt=0)
    date: date_type
    category: str | None = None
    payment_method: str | None = None
    note: str | None = None


class ExpenseImportCommit(BaseModel):
    rows: list[ExpenseImportRow] = Field(max_length=5000)
