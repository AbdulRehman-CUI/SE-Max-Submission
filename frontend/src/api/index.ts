import { allPages, json, request } from "../lib/api";
import type {
  Anomaly,
  Budget,
  BudgetInput,
  BudgetSummary,
  Expense,
  ExpenseInput,
  Insights,
  MonthSummary,
  ParseResult,
  SMSResult,
  Summary,
  Trend,
  User,
} from "../types/api";
export const auth = {
  me: () => request<User>("/auth/me"),
  login: (identifier: string, password: string) =>
    request<{ access_token: string; token_type: string }>(
      "/auth/login",
      json("POST", {
        [identifier.includes("@") ? "email" : "username"]: identifier,
        password,
      }),
    ),
  register: (username: string, email: string, password: string) =>
    request<User>(
      "/auth/register",
      json("POST", { username, email, password }),
    ),
};
export const expenses = {
  list: () => allPages<Expense>("/expenses"),
  recent: () => request<Expense[]>("/expenses?limit=5"),
  create: (body: ExpenseInput) =>
    request<Expense>("/expenses", json("POST", body)),
  update: (id: string, body: ExpenseInput) =>
    request<Expense>(`/expenses/${id}`, json("PATCH", body)),
  remove: (id: string) =>
    request<void>(`/expenses/${id}`, { method: "DELETE" }),
};
export const budgets = {
  list: () => allPages<Budget>("/budgets"),
  create: (body: BudgetInput) =>
    request<Budget>("/budgets", json("POST", body)),
  update: (id: string, budget_limit: string) =>
    request<Budget>(`/budgets/${id}`, json("PATCH", { budget_limit })),
  remove: (id: string) => request<void>(`/budgets/${id}`, { method: "DELETE" }),
  summary: (id: string) => request<BudgetSummary>(`/budgets/${id}/summary`),
};
const periodQuery = (period: string) =>
  `year=${Number(period.slice(0, 4))}&month=${Number(period.slice(5, 7))}`;
export const analytics = {
  summary: () => request<Summary>("/analytics/summary"),
  month: (period: string) =>
    request<MonthSummary>(`/v2/analytics/monthly?${periodQuery(period)}`),
  trends: (period: string) => {
    const months = Math.min(6, (Number(period.slice(0, 4)) - 1) * 12 + Number(period.slice(5)));
    return request<Trend[]>(`/v2/analytics/trends?months=${months}&end_month=${period}-01`);
  },
  insights: (period: string) =>
    request<Insights>(`/v2/analytics/insights?${periodQuery(period)}`),
  check: (
    body: Pick<
      ExpenseInput,
      "amount" | "category" | "transaction_date" | "currency"
    >,
  ) => request<Anomaly>("/v2/analytics/anomalies/check", json("POST", body)),
};
export const parsing = {
  text: (text: string) =>
    request<ParseResult>("/expenses/parse", json("POST", { text })),
  sms: (text: string) =>
    request<SMSResult>("/expenses/parse-sms", json("POST", { text })),
};
