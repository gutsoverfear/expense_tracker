# Expense Tracker Backend

FastAPI backend for the multi-user expense tracker. PostgreSQL is configured through `DATABASE_URL`; amounts are stored as integer paise.

## Run locally

1. Create and activate a virtual environment:

   ```powershell
   cd backend
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies and configure environment variables:

   ```powershell
   pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

   Set `DATABASE_URL` to a running PostgreSQL database and replace `JWT_SECRET_KEY` in `.env`.

3. Apply the initial migration:

   ```powershell
   alembic upgrade head
   ```

4. Start the API:

   ```powershell
   uvicorn app.main:app --reload
   ```

The API is available at `http://localhost:8000`. Interactive documentation is at `http://localhost:8000/docs`.

## Auth endpoints

- `POST /auth/register` with `{ "email": "you@example.com", "password": "at-least-8-characters" }`
- `POST /auth/login` with the same fields; returns a bearer JWT
- `GET /auth/me` with `Authorization: Bearer <token>`

Registration creates the default categories `Food`, `Grocery`, `Rapido`, `Extra-curricular`, and `Others`, plus payment methods `UPI`, `Cash`, and `Credit Card`.

## Authenticated CRUD

All resource endpoints require `Authorization: Bearer <token>` and scope database queries to the authenticated user.

- Categories: `GET|POST /categories`, `GET|PUT|DELETE /categories/{category_id}`
- Payment methods: `GET|POST /payment-methods`, `GET|PUT|DELETE /payment-methods/{payment_method_id}`
- Expenses: `POST /expenses`, `GET|PUT|DELETE /expenses/{expense_id}`
- Expense list filters: `start_date`, `end_date`, `category_id`, `payment_method_id`, `skip`, and `limit`
- Export: `GET /expenses/export` returns all of the authenticated user's expenses as CSV.
- Import preview: `POST /expenses/import/preview` accepts a CSV file and a JSON column mapping, then returns validated preview rows.
- Import commit: `POST /expenses/import` saves the preview rows after category and payment-method ownership validation.

Expense amounts use integer paise. Category and payment method references are also checked for ownership when creating or updating an expense.

## Deployment

### Neon database

Create a PostgreSQL project on [Neon](https://neon.tech), copy its pooled connection string, and set it as `DATABASE_URL`. The SQLAlchemy URL should use the `postgresql+psycopg://` scheme; append `?sslmode=require` when needed.

### Render backend

Create a Render Web Service connected to this repository with:

- Root directory: `backend`
- Environment: Docker
- Dockerfile: `backend/Dockerfile`

Set these Render environment variables:

```text
DATABASE_URL=<Neon connection string>
JWT_SECRET_KEY=<long random secret>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=https://<your-vercel-app>.vercel.app
```

The Docker entrypoint runs `alembic upgrade head` before starting Uvicorn and uses Render's `PORT` automatically. Verify the deployment at `/health`.

### Vercel frontend

Import the repository into Vercel with:

- Root directory: `frontend`
- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`

Set `VITE_API_URL` to the Render backend URL, for example `https://expense-api.onrender.com`. The included `vercel.json` rewrites client-side routes to `index.html` so protected routes work after refresh.

After deployment, update Render's `CORS_ORIGINS` to the final Vercel URL. For multiple frontend origins, separate them with commas.
