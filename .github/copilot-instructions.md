Project: multi-user expense tracker PWA.
Stack: FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Pydantic v2, JWT auth (bcrypt).
Frontend: React + Vite + TypeScript + Tailwind + Recharts + React Query.
Monorepo: /backend and /frontend.
Rules: every DB query must filter by the authenticated user's id. Amounts stored as integer paise. Use type hints, small functions, env vars for secrets. Never hardcode secrets.