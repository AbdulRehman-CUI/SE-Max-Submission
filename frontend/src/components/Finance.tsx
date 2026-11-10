import { Pencil, Trash2 } from "lucide-react";
import type { Budget, Expense, Insights } from "../types/api";
import { cents, dateLabel, money } from "../lib/format";
import { Button, Empty } from "./ui";
export function ExpenseTable({
  rows,
  onEdit,
  onDelete,
}: {
  rows: Expense[];
  onEdit?: (expense: Expense) => void;
  onDelete?: (expense: Expense) => void;
}) {
  if (!rows.length)
    return (
      <Empty title="No expenses here yet">
        Record an expense or adjust your filters to see it here.
      </Empty>
    );
  return (
    <div className="table-scroll">
      <table>
        <caption className="sr-only">Recorded expenses</caption>
        <thead>
          <tr>
            <th scope="col">Transaction</th>
            <th scope="col">Category</th>
            <th scope="col">Date</th>
            <th scope="col" className="align-right">
              Amount
            </th>
            {onEdit && (
              <th scope="col">
                <span className="sr-only">Actions</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((expense) => (
            <tr key={expense.id}>
              <td>
                <div className="transaction">
                  <span className="transaction-icon">
                    {expense.category.slice(0, 1).toUpperCase()}
                  </span>
                  <div>
                    <strong>{expense.description || expense.category}</strong>
                    <small>
                      {expense.payment_method || "Payment method not set"}
                    </small>
                  </div>
                </div>
              </td>
              <td>
                <span className="badge">{expense.category}</span>
              </td>
              <td className="nowrap">{dateLabel(expense.transaction_date)}</td>
              <td className="align-right nowrap amount">
                {money(expense.amount, expense.currency)}
              </td>
              {onEdit && (
                <td>
                  <div className="row-actions">
                    <Button
                      variant="ghost"
                      aria-label={`Edit ${expense.description || expense.category}`}
                      onClick={() => onEdit(expense)}
                    >
                      <Pencil size={16} />
                    </Button>
                    <Button
                      variant="ghost"
                      aria-label={`Delete ${expense.description || expense.category}`}
                      onClick={() => onDelete?.(expense)}
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function BudgetCard({
  budget,
  onEdit,
  onDelete,
  onView,
}: {
  budget: Pick<Budget, "category" | "budget_limit" | "total_spent" | "remaining_budget">;
  onEdit?: () => void;
  onDelete?: () => void;
  onView?: () => void;
}) {
  const over =
    budget.remaining_budget != null && cents(budget.remaining_budget) < 0n;
  const percent =
    budget.total_spent === null
      ? null
      : Number(budget.budget_limit) === 0
        ? Number(budget.total_spent) > 0
          ? 100
          : 0
        : Math.min(
            100,
            (Number(budget.total_spent) / Number(budget.budget_limit)) * 100,
          );
  return (
    <article className={`budget-card ${over ? "over-budget" : ""}`}>
      <div className="section-heading">
        <h3>{budget.category}</h3>
        {onEdit && (
          <div className="row-actions">
            <Button
              variant="ghost"
              aria-label={`Edit ${budget.category} budget`}
              onClick={onEdit}
            >
              <Pencil size={16} />
            </Button>
            <Button
              variant="ghost"
              aria-label={`Delete ${budget.category} budget`}
              onClick={onDelete}
            >
              <Trash2 size={16} />
            </Button>
          </div>
        )}
      </div>
      <div className="budget-amount">
        <strong>{money(budget.total_spent)}</strong>
        <span>of {money(budget.budget_limit)}</span>
      </div>
      {percent !== null && (
        <div
          className="progress-track"
          role="progressbar"
          aria-label={`${budget.category} budget used`}
          aria-valuenow={Math.round(percent)}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <span style={{ width: `${percent}%` }} />
        </div>
      )}
      <p className={over ? "overspent" : "muted"}>
        {money(budget.remaining_budget)} remaining{" "}
        {over && <strong>· Over budget</strong>}
      </p>
      {onView && <Button variant="ghost" onClick={onView} aria-label={`View ${budget.category} budget summary`}>View summary</Button>}
    </article>
  );
}
export function InsightsContent({
  data,
  preview = false,
}: {
  data: Insights;
  preview?: boolean;
}) {
  return (
    <div className="insights-content">
      <span className="source-label">
        {data.is_fallback || data.generated_by !== "gemini"
          ? "Insights based on your spending statistics"
          : "AI-generated insights"}
      </span>
      <p className="insight-summary">{data.summary}</p>
      {data.period.is_partial && (
        <span className="badge">
          Month in progress · through {dateLabel(data.period.through_date)}
        </span>
      )}
      <div className="insight-list">
        {[...data.warnings, ...data.insights]
          .slice(0, preview ? 2 : undefined)
          .map((item, index) => (
            <article
              key={`${item.type}-${index}`}
              className={`insight-item ${item.severity === "warning" ? "warning" : ""}`}
            >
              <span className="insight-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.message}</p>
                {item.severity === "warning" && (
                  <small>Budget or spending warning</small>
                )}
              </div>
            </article>
          ))}
      </div>
    </div>
  );
}
