import { useCallback, useState, type FormEvent } from "react";
import { analytics, expenses, budgets } from "../api";
import { CategoryChart, TrendChart } from "../components/Charts";
import { BudgetCard } from "../components/Finance";
import {
  Button,
  Empty,
  ErrorMessage,
  Field,
  Loading,
  MonthPicker,
  PageHeading,
  Stat,
} from "../components/ui";
import { useResource } from "../hooks/useResource";
import { dateLabel, message, money, monthLabel, today } from "../lib/format";
import type { Anomaly } from "../types/api";

function AnomalyCheck({ period }: { period: string }) {
  const resource = useResource(expenses.list);
  const [id, setId] = useState("");
  const [result, setResult] = useState<Anomaly>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const candidates =
    resource.data?.filter(
      (expense) =>
        expense.transaction_date.startsWith(period) &&
        expense.transaction_date <= today(),
    ) || [];
  const candidate = candidates.find((expense) => expense.id === id);
  async function check(event: FormEvent) {
    event.preventDefault();
    if (!candidate) return;
    setBusy(true);
    setError("");
    setResult(undefined);
    const { amount, category, currency, transaction_date } = candidate;
    try {
      setResult(
        await analytics.check({ amount, category, currency, transaction_date }),
      );
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  const status = {
    unusual: "Unusual spending",
    normal: "Within the usual range",
    insufficient_history: "Insufficient history",
    unavailable_baseline: "Baseline unavailable",
  };
  return (
    <section className="card panel">
      <h2>Unusual spending</h2>
      <p className="muted">
        Compare an expense with your earlier transactions in the same category
        and currency.
      </p>
      {resource.loading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorMessage error={resource.error} retry={resource.reload} />
      ) : !candidates.length ? (
        <Empty title="No transactions to check">
          Choose a month with recorded expenses to compare.
        </Empty>
      ) : (
        <form onSubmit={check} className="anomaly-form">
          <Field label="Transaction">
            <select
              value={id}
              required
              disabled={busy}
              onChange={(event) => {
                setId(event.target.value);
                setResult(undefined);
                setError("");
              }}
            >
              <option value="">Choose an expense</option>
              {candidates.map((expense) => (
                <option key={expense.id} value={expense.id}>
                  {expense.description || expense.category} ·{" "}
                  {dateLabel(expense.transaction_date)} ·{" "}
                  {money(expense.amount, expense.currency)}
                </option>
              ))}
            </select>
          </Field>
          <Button type="submit" busy={busy} disabled={!candidate}>
            Check transaction
          </Button>
        </form>
      )}
      <ErrorMessage error={error} />
      {result && (
        <div role="status" className="notice">
          <strong>
            {status[result.status]} · {result.category} ·{" "}
            {money(result.amount, result.currency)}
          </strong>
          <p>{result.explanation}</p>
          {result.is_unusual && (
            <p>
              Review the transaction details. This is a comparison with your
              previous spending.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

export default function AnalyticsPage() {
  const [period, setPeriod] = useState(today().slice(0, 7));
  const month = useResource(
    useCallback(() => analytics.month(period), [period]),
  );
  const trends = useResource(
    useCallback(() => analytics.trends(period), [period]),
  );
  const budgetRows = useResource(budgets.list);
  const selectedBudgets =
    budgetRows.data?.filter(
      (row) =>
        row.year === Number(period.slice(0, 4)) &&
        row.month === Number(period.slice(5)),
    ) || [];
  const current = trends.data?.at(-1);
  const previous = trends.data?.at(-2);
  return (
    <>
      <PageHeading
        eyebrow="THE BIGGER PICTURE"
        title="Spending analytics"
        description="Explore your spending patterns and the categories behind them."
      >
        <MonthPicker value={period} onChange={setPeriod} />
      </PageHeading>
      <div className="section-heading period-heading">
        <h2>{monthLabel(period)}</h2>
        {month.data?.is_partial && (
          <span className="badge">
            Month in progress · through {dateLabel(month.data.through_date)}
          </span>
        )}
      </div>
      {month.loading ? (
        <Loading />
      ) : month.error ? (
        <ErrorMessage error={month.error} retry={month.reload} />
      ) : (
        month.data && (
          <div className="stats-grid">
            <Stat
              label="Monthly spending"
              value={money(month.data.total_spent)}
              note="Recorded in PKR"
              accent
            />
            <Stat
              label="Transactions"
              value={month.data.transaction_count}
              note="Recorded in PKR"
            />
            <Stat
              label="Average expense"
              value={
                month.data.average_expense === null
                  ? "No expenses"
                  : money(month.data.average_expense)
              }
              note="Per PKR transaction"
            />
            <Stat
              label="Previous-month change"
              value={
                trends.loading
                  ? "…"
                  : trends.error
                    ? "Unavailable"
                    : current?.change_percentage != null
                      ? `${current.change_percentage}%`
                      : "No baseline"
              }
              note={
                previous
                  ? `Previous month: ${money(previous.total_spent)}`
                  : "A prior month is needed for comparison"
              }
            />
          </div>
        )
      )}
      <div className="overview-grid">
        <section className="card panel">
          <h2>Monthly trend</h2>
          <p className="muted">Recorded spending in PKR</p>
          {trends.loading ? (
            <Loading />
          ) : trends.error ? (
            <ErrorMessage error={trends.error} retry={trends.reload} />
          ) : (
            <TrendChart data={trends.data ?? []} />
          )}
        </section>
        <section className="card panel">
          <h2>Category breakdown</h2>
          <p className="muted">Your spending mix for {monthLabel(period)}</p>
          {month.loading ? (
            <Loading />
          ) : month.error ? (
            <ErrorMessage error={month.error} retry={month.reload} />
          ) : (
            <CategoryChart data={month.data?.categories ?? []} />
          )}
        </section>
      </div>
      <section className="card panel">
        <h2>Budget utilization</h2>
        <p className="muted">Progress across this month’s category budgets</p>
        {budgetRows.loading ? (
          <Loading />
        ) : budgetRows.error ? (
          <ErrorMessage error={budgetRows.error} retry={budgetRows.reload} />
        ) : selectedBudgets.length ? (
          <div className="budget-grid">
            {selectedBudgets.map((budget) => (
              <BudgetCard budget={budget} key={budget.id} />
            ))}
          </div>
        ) : (
          <Empty title="No budgets for this month">
            Create a monthly budget to see utilization.
          </Empty>
        )}
      </section>
      <AnomalyCheck key={period} period={period} />
    </>
  );
}
