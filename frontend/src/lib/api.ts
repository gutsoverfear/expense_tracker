import axios from 'axios'

const apiBaseUrl = import.meta.env.VITE_API_URL
	?? (import.meta.env.PROD ? 'https://expense-api-mobt.onrender.com' : 'http://localhost:8000')

export const api = axios.create({ baseURL: apiBaseUrl, headers: { 'Content-Type': 'application/json' } })
api.interceptors.request.use((config) => { const token = localStorage.getItem('expense_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })
api.interceptors.response.use((response) => response, (error) => { if (error.response?.status === 401) localStorage.removeItem('expense_token'); return Promise.reject(error) })

export type User = { id: number; email: string; created_at: string }
export type TokenResponse = { access_token: string; token_type: string }
export type Category = { id: number; name: string; icon?: string | null }
export type PaymentMethod = { id: number; name: string }
export type Expense = { id: number; amount_paise: number; date: string; category_id?: number | null; payment_method_id?: number | null; note?: string | null; created_at: string }
export type ExpensePayload = { amount_paise: number; date: string; category_id?: number | null; payment_method_id?: number | null; note?: string | null }
export type SpendingBreakdown = { label: string; amount_paise: number }
export type DailySpending = { date: string; amount_paise: number }
export type ExpenseSummary = { month: string; total: { amount_paise: number }; by_category: SpendingBreakdown[]; by_payment_method: SpendingBreakdown[]; daily: DailySpending[]; top_expenses: Expense[] }
export type Budget = { id: number; category_id: number; category_name: string; month: string; limit_paise: number; spent_paise: number; percentage: number }
export type RecurringExpense = { id: number; amount_paise: number; category_id?: number | null; payment_method_id?: number | null; note?: string | null; frequency: 'daily' | 'weekly' | 'monthly'; next_run_date: string; active: boolean; created_at: string }
export const authApi = { register: (email: string, password: string) => api.post<User>('/auth/register', { email, password }), login: (email: string, password: string) => api.post<TokenResponse>('/auth/login', { email, password }), me: () => api.get<User>('/auth/me') }