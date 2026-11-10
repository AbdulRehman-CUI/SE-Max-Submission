import { useCallback } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Plus, Sparkles } from "lucide-react";
import { analytics, budgets, expenses } from "../api";
import { CategoryChart, TrendChart } from "../components/Charts";
import {
  BudgetCard,
  ExpenseTable,
  InsightsContent,
} from "../components/Finance";
import {
  Empty,
  ErrorMessage,
  Loading,
  PageHeading,
  Stat,
} from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useResource } from "../hooks/useResource";
import { dateLabel, money, sumMoney, today } from "../lib/format";

export default function DashboardPage() {
  const { user } = useAuth();
  const period = today().slice(0, 7);
  const summary = useResource(analytics.summary);
  const recent = useResource(expenses.recent);
  const budgetRows = useResource(budgets.list);
  const month = useResource(
    useCallback(() => analytics.month(period), [period]),
  );
  const trend = useResource(
    useCallback(() => analytics.trends(period), [period]),
  );
  const insights = useResource(
    useCallback(() => analytics.insights(period), [period]),
  );
  const currentBudgets = budgetRows.data?.filter(
    (row) =>
      row.year === Number(period.slice(0, 4)) &&
      row.month === Number(period.slice(5)),
  );
  const remaining =
    currentBudgets?.length &&
    currentBudgets.every((row) => row.remaining_budget !== null)
      ? money(sumMoney(currentBudgets.map((row) => row.remaining_budget!)))
      : null;
  return (
    <>
      <PageHeading
        eyebrow="YOUR FINANCES AT A GLANCE"
        title={`Hello, ${user?.username}.`}
        description="Here’s what your spending looks like today."
      >
        <Link to="/expenses?new=1" className="btn btn-primary">
          <Plus size={18} />
          Add expense
        </Link>
      </PageHeading>
      <div className="stats-grid">
        <Stat
          label="Total spending"
          value={summary.loading ? "…" : money(summary.data?.total_spent)}
          note="All recorded PKR expenses"
          accent
        />
        <Stat
          label="This month’s spending"
          value={
            summary.loading ? "…" : money(summary.data?.current_month_spending)
          }
          note={
            summary.data
              ? `Through ${dateLabel(summary.data.through_date)}`
              : "PKR expenses"
          }
        />
        <Stat
          label="Remaining budget"
          value={
            budgetRows.loading
              ? "…"
              : (remaining ??
                (currentBudgets?.length === 0 ? "No budgets" : "Unavailable"))
          }
          note="Across this month’s budgets"
        />
        <Stat
          label="Total transactions"
          value={
            summary.loading
              ? "…"
              : (summary.data?.total_transactions ?? "Unavailable")
          }
          note="All recorded PKR transactions"
        />
      </div>
      <ErrorMessage error={summary.error} retry={summary.reload} />
      <div className="overview-grid">
        <section className="card panel">
          <h2>Spending over time</h2>
          <p className="muted">Six months of recorded PKR spending</p>
          {trend.loading ? (
            <Loading />
          ) : trend.error ? (
            <ErrorMessage error={trend.error} retry={trend.reload} />
          ) : (
            <TrendChart data={trend.data ?? []} />
          )}
        </section>
        <section className="card panel">
          <h2>Spending by category</h2>
          <p className="muted">This month’s PKR expenses</p>
          {month.loading ? (
            <Loading />
          ) : month.error ? (
            <ErrorMessage error={month.error} retry={month.reload} />
          ) : (
            <CategoryChart data={month.data?.categories ?? []} />
          )}
        </section>
      </div>
      <section className="card">
        <div className="section-heading panel-heading">
          <h2>Recent expenses</h2>
          <Link className="text-link" to="/expenses">
            View all <ArrowRight size={15} />
          </Link>
        </div>
        {recent.loading ? (
          <Loading />
        ) : recent.error ? (
          <ErrorMessage error={recent.error} retry={recent.reload} />
        ) : (
          <ExpenseTable rows={recent.data ?? []} />
        )}
      </section>
      <div className="overview-grid lower-grid">
        <section className="card panel">
          <div className="section-heading">
            <h2>Budget progress</h2>
            <Link className="text-link" to="/budgets">
              View budgets <ArrowRight size={15} />
            </Link>
          </div>
          {budgetRows.loading ? (
            <Loading />
          ) : budgetRows.error ? (
            <ErrorMessage error={budgetRows.error} retry={budgetRows.reload} />
          ) : currentBudgets?.length ? (
            <div className="budget-stack">
              {currentBudgets.slice(0, 3).map((budget) => (
                <BudgetCard key={budget.id} budget={budget} />
              ))}
            </div>
          ) : (
            <Empty title="No budgets this month">
              Create a monthly category budget to track your progress.
            </Empty>
          )}
        </section>
        <section className="card panel">
          <div className="section-heading">
            <h2>
              <Sparkles size={19} />
              Insights preview
            </h2>
            <Link className="text-link" to="/insights">
              All insights <ArrowRight size={15} />
            </Link>
          </div>
          {insights.loading ? (
            <Loading />
          ) : insights.error ? (
            <ErrorMessage error={insights.error} retry={insights.reload} />
          ) : (
            insights.data && <InsightsContent data={insights.data} preview />
          )}
        </section>
      </div>
    </>
  );
}
