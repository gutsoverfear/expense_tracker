from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Expense, RecurringExpense
from app.services.recurring import generate_due_recurring_expenses
from tests.conftest import register


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_user_cannot_read_edit_or_delete_another_users_data(client: TestClient):
    user_a = register(client, "a@example.com")
    user_b = register(client, "b@example.com")
    headers_a = auth_header(user_a)
    headers_b = auth_header(user_b)

    category = client.post("/categories", json={"name": "Private A"}, headers=headers_a).json()
    payment_method = client.post(
        "/payment-methods", json={"name": "Private Card A"}, headers=headers_a
    ).json()
    expense = client.post(
        "/expenses",
        json={
            "amount_paise": 1250,
            "date": str(date.today()),
            "category_id": category["id"],
            "payment_method_id": payment_method["id"],
            "note": "private",
        },
        headers=headers_a,
    ).json()

    assert client.get(f"/categories/{category['id']}", headers=headers_b).status_code == 404
    assert client.put(
        f"/categories/{category['id']}", json={"name": "Stolen"}, headers=headers_b
    ).status_code == 404
    assert client.delete(f"/categories/{category['id']}", headers=headers_b).status_code == 404

    assert client.get(
        f"/payment-methods/{payment_method['id']}", headers=headers_b
    ).status_code == 404
    assert client.put(
        f"/payment-methods/{payment_method['id']}",
        json={"name": "Stolen"},
        headers=headers_b,
    ).status_code == 404
    assert client.delete(
        f"/payment-methods/{payment_method['id']}", headers=headers_b
    ).status_code == 404

    assert client.get(f"/expenses/{expense['id']}", headers=headers_b).status_code == 404
    assert client.put(
        f"/expenses/{expense['id']}", json={"amount_paise": 1}, headers=headers_b
    ).status_code == 404
    assert client.delete(f"/expenses/{expense['id']}", headers=headers_b).status_code == 404

    assert client.get("/expenses", headers=headers_b).json() == []
    assert client.get(f"/expenses/{expense['id']}", headers=headers_a).json()["amount_paise"] == 1250


def test_expense_list_filters_and_pagination_are_user_scoped(client: TestClient):
    user_a = register(client, "filters-a@example.com")
    user_b = register(client, "filters-b@example.com")
    headers_a = auth_header(user_a)
    headers_b = auth_header(user_b)

    category = client.post("/categories", json={"name": "Filtered"}, headers=headers_a).json()
    payment_method = client.post(
        "/payment-methods", json={"name": "Filtered Pay"}, headers=headers_a
    ).json()
    for amount, expense_date in [(100, "2026-01-01"), (200, "2026-02-01")]:
        response = client.post(
            "/expenses",
            json={
                "amount_paise": amount,
                "date": expense_date,
                "category_id": category["id"],
                "payment_method_id": payment_method["id"],
            },
            headers=headers_a,
        )
        assert response.status_code == 201

    other_category = client.post(
        "/categories", json={"name": "B category"}, headers=headers_b
    ).json()
    client.post(
        "/expenses",
        json={"amount_paise": 999, "date": "2026-02-01", "category_id": other_category["id"]},
        headers=headers_b,
    )

    response = client.get(
        "/expenses?start_date=2026-02-01&category_id="
        f"{category['id']}&payment_method_id={payment_method['id']}&limit=1",
        headers=headers_a,
    )
    assert response.status_code == 200
    assert [item["amount_paise"] for item in response.json()] == [200]


def test_monthly_summary_uses_sql_aggregates_and_is_user_scoped(client: TestClient):
    user_a = register(client, "summary-a@example.com")
    user_b = register(client, "summary-b@example.com")
    headers_a = auth_header(user_a)
    headers_b = auth_header(user_b)
    category = client.post("/categories", json={"name": "Summary food"}, headers=headers_a).json()
    method = client.post("/payment-methods", json={"name": "Summary UPI"}, headers=headers_a).json()

    for amount, expense_date in [(100, "2026-03-01"), (250, "2026-03-01"), (900, "2026-03-15")]:
        response = client.post(
            "/expenses",
            json={
                "amount_paise": amount,
                "date": expense_date,
                "category_id": category["id"],
                "payment_method_id": method["id"],
            },
            headers=headers_a,
        )
        assert response.status_code == 201

    client.post(
        "/expenses",
        json={"amount_paise": 5000, "date": "2026-03-20"},
        headers=headers_b,
    )
    summary = client.get("/expenses/summary?month=2026-03", headers=headers_a)

    assert summary.status_code == 200
    data = summary.json()
    assert data["total"] == {"amount_paise": 1250}
    assert data["by_category"] == [{"label": "Summary food", "amount_paise": 1250}]
    assert data["by_payment_method"] == [{"label": "Summary UPI", "amount_paise": 1250}]
    assert data["daily"] == [
        {"date": "2026-03-01", "amount_paise": 350},
        {"date": "2026-03-15", "amount_paise": 900},
    ]
    assert [expense["amount_paise"] for expense in data["top_expenses"]] == [900, 250, 100]


def test_recurring_generation_is_idempotent_and_scoped(client: TestClient):
    token = register(client, "recurring@example.com")
    headers = auth_header(token)
    response = client.post(
        "/recurring-expenses",
        json={
            "amount_paise": 750,
            "frequency": "weekly",
            "next_run_date": "2026-03-01",
            "note": "Weekly train",
        },
        headers=headers,
    )
    assert response.status_code == 201

    from app.database import SessionLocal

    with SessionLocal() as session:
        recurring = session.scalar(select(RecurringExpense).where(RecurringExpense.note == "Weekly train"))
        assert recurring is not None
        assert generate_due_recurring_expenses(session, run_date=date(2026, 3, 15)) == 3
        assert generate_due_recurring_expenses(session, run_date=date(2026, 3, 15)) == 0
        assert len(session.scalars(select(Expense).where(Expense.recurring_expense_id == recurring.id)).all()) == 3


def test_csv_export_and_import_preview_are_user_scoped(client: TestClient):
    user_a = register(client, "csv-a@example.com")
    user_b = register(client, "csv-b@example.com")
    headers_a = auth_header(user_a)
    headers_b = auth_header(user_b)
    category = client.post("/categories", json={"name": "CSV food"}, headers=headers_a).json()
    method = client.post("/payment-methods", json={"name": "CSV cash"}, headers=headers_a).json()
    client.post(
        "/expenses",
        json={"amount_paise": 1234, "date": "2026-04-02", "category_id": category["id"], "payment_method_id": method["id"], "note": "Lunch"},
        headers=headers_a,
    )
    client.post("/expenses", json={"amount_paise": 9999, "date": "2026-04-02"}, headers=headers_b)

    exported = client.get("/expenses/export", headers=headers_a)
    assert exported.status_code == 200
    assert "1234" in exported.text
    assert "9999" not in exported.text

    preview = client.post(
        "/expenses/import/preview",
        files={"file": ("expenses.csv", "value,when,kind,paid_with,memo\n500,2026-04-03,CSV food,CSV cash,Coffee\n", "text/csv")},
        data={"mapping": '{"amount_paise":"value","date":"when","category":"kind","payment_method":"paid_with","note":"memo"}'},
        headers=headers_a,
    )
    assert preview.status_code == 200
    assert preview.json()["total_rows"] == 1
    assert preview.json()["errors"] == []

    committed = client.post("/expenses/import", json={"rows": preview.json()["rows"]}, headers=headers_a)
    assert committed.status_code == 200
    assert committed.json() == {"imported": 1}
    expenses = client.get("/expenses", headers=headers_a).json()
    assert sorted(item["amount_paise"] for item in expenses) == [500, 1234]