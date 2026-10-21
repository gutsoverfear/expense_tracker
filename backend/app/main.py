from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.categories import router as categories_router
from app.routers.expenses import router as expenses_router
from app.routers.payment_methods import router as payment_methods_router
from app.routers.budgets import router as budgets_router
from app.routers.recurring import router as recurring_router
from app.database import SessionLocal
from app.config import get_settings
from app.services.recurring import generate_due_recurring_expenses

scheduler = BackgroundScheduler()


def run_recurring_job() -> None:
    with SessionLocal() as session:
        generate_due_recurring_expenses(session)


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler.add_job(run_recurring_job, "interval", hours=1, id="generate-recurring", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)

app = FastAPI(title="Expense Tracker API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(categories_router)
app.include_router(payment_methods_router)
app.include_router(expenses_router)
app.include_router(budgets_router)
app.include_router(recurring_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
