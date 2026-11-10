export interface User {
  id: string;
  username: string;
  email: string;
  created_at: string;
}
export interface ExpenseInput {
  amount: string;
  category: string;
  description: string | null;
  transaction_date: string;
  currency: string;
  payment_method: string | null;
}
export interface Expense extends ExpenseInput {
  id: string;
  user_id: string;
  created_at: string;
}
export interface BudgetInput {
  category: string;
  budget_limit: string;
  month: number;
  year: number;
}
export interface Budget extends BudgetInput {
  id: string;
  total_spent: string | null;
  remaining_budget: string | null;
}
export interface BudgetSummary extends BudgetInput {
  budget_id: string;
  total_spent: string;
  remaining_budget: string;
}
export interface Summary {
  total_spent: string;
  total_transactions: number;
  average_transaction: string;
  current_month_spending: string;
  previous_month_spending: string;
  spending_change_percentage: string | null;
  is_partial: boolean;
  through_date: string;
}
export interface Category {
  category: string | null;
  total_spent: string;
  transaction_count: number;
  percentage_of_total: string;
}
export interface MonthSummary {
  year: number;
  month: number;
  currency: string;
  total_spent: string;
  transaction_count: number;
  average_expense: string | null;
  categories: Category[];
  is_partial: boolean;
  through_date: string;
}
export interface Trend extends MonthSummary {
  change_amount: string | null;
  change_percentage: string | null;
}
export interface Insight {
  type: string;
  title: string;
  message: string;
  severity: "info" | "warning";
}
export interface Insights {
  summary: string;
  insights: Insight[];
  warnings: Insight[];
  period: {
    year: number;
    month: number;
    through_date: string;
    is_partial: boolean;
  };
  currency: string;
  generated_by: "gemini" | "deterministic";
  is_fallback: boolean;
}
export interface ParseResult {
  extracted_fields: Partial<{
    [K in keyof ExpenseInput]: ExpenseInput[K] | null;
  }>;
  missing_fields: string[];
  confirmation_required: true;
}
export interface SMSResult extends ParseResult {
  transaction_type: string;
  transaction_status: string;
  amount: string | null;
  currency: string | null;
  transaction_date: string | null;
  merchant: string | null;
  transaction_reference: string | null;
  source: string | null;
  is_expense_candidate: boolean;
  clarification_required: boolean;
}
export interface Anomaly {
  expense_id: string | null;
  status:
    "insufficient_history" | "unavailable_baseline" | "normal" | "unusual";
  is_unusual: boolean;
  has_enough_history: boolean;
  category: string;
  currency: string;
  amount: string;
  sample_count: number;
  minimum_history: number;
  explanation: string;
}
