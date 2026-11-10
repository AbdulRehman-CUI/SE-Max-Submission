import { useCallback, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { budgets } from "../api";
import { BudgetCard } from "../components/Finance";
import {
  Button,
  Empty,
  ErrorMessage,
  Field,
  Loading,
  Modal,
  MonthPicker,
  PageHeading,
  useToast,
} from "../components/ui";
import { useResource } from "../hooks/useResource";
import { message, monthLabel, today, validMoney } from "../lib/format";
import type { Budget } from "../types/api";
function BudgetForm({
  initial,
  period,
  onSaved,
  onBusy,
}: {
  initial?: Budget;
  period: string;
  onSaved: (period: string) => void;
  onBusy: (busy: boolean) => void;
}) {
  const [limit, setLimit] = useState(initial?.budget_limit ?? "");
  const [category, setCategory] = useState(initial?.category ?? "");
  const [month, setMonth] = useState(period);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!validMoney(limit, true)) {
      setError(
        "Enter a non-negative limit with up to 10 whole digits and 2 decimal places.",
      );
      return;
    }
    if (!category.trim()) {
      setError("Enter a category.");
      return;
    }
    setBusy(true);
    onBusy(true);
    setError("");
    try {
      if (initial) await budgets.update(initial.id, limit);
      else
        await budgets.create({
          category: category.trim(),
          budget_limit: limit,
          year: Number(month.slice(0, 4)),
          month: Number(month.slice(5)),
        });
      onSaved(month);
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
      onBusy(false);
    }
  }
  return (
    <form className="form-stack" onSubmit={submit}>
      <ErrorMessage error={error} />
      <fieldset disabled={busy}>
        <Field label="Category">
          <input
            required
            maxLength={100}
            disabled={!!initial}
            placeholder="e.g. Food"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          />
        </Field>
        <Field label="Budget month">
          <input
            type="month"
            min="0001-01"
            max="9999-12"
            required
            disabled={!!initial}
            value={month}
            onChange={(event) => setMonth(event.target.value)}
          />
        </Field>
        <Field label="Monthly limit (PKR)">
          <input
            required
            inputMode="decimal"
            maxLength={13}
            placeholder="0.00"
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
          />
        </Field>
        <p className="form-note">
          Your budget includes all spending in this category for the whole
          month. Changing the limit keeps your spending intact.
        </p>
        <Button busy={busy} type="submit">
          {initial ? "Update budget" : "Create budget"}
        </Button>
      </fieldset>
    </form>
  );
}
function BudgetDetails({ budget, onClose }: { budget: Budget; onClose: () => void }) {
  const resource = useResource(useCallback(() => budgets.summary(budget.id), [budget.id]));
  return <Modal title={`${budget.category} budget summary`} onClose={onClose}>
    {resource.loading ? <Loading/> : resource.error ? <ErrorMessage error={resource.error} retry={resource.reload}/> : resource.data && <BudgetCard budget={resource.data}/>}
  </Modal>;
}

export default function BudgetsPage() {
  const resource = useResource(budgets.list);
  const toast = useToast();
  const [period, setPeriod] = useState(today().slice(0, 7));
  const [edit, setEdit] = useState<Budget | "new" | null>(null);
  const [deleting, setDeleting] = useState<Budget | null>(null);
  const [details, setDetails] = useState<Budget | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const rows =
    resource.data?.filter(
      (row) =>
        row.year === Number(period.slice(0, 4)) &&
        row.month === Number(period.slice(5)),
    ) || [];
  async function remove() {
    if (!deleting) return;
    setBusy(true);
    try {
      await budgets.remove(deleting.id);
      setDeleting(null);
      resource.reload();
      toast("Budget deleted. Your expenses are unchanged.");
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="A PLAN FOR YOUR PRIORITIES"
        title="Monthly budgets"
        description="Make a little room for the things that matter."
      >
        <Button onClick={() => setEdit("new")}>
          <Plus size={18} />
          Create budget
        </Button>
      </PageHeading>
      <div className="section-heading period-heading">
        <div>
          <h2>{monthLabel(period)}</h2>
          <p className="muted">PKR budgets · whole-month spending</p>
        </div>
        <MonthPicker value={period} onChange={setPeriod} />
      </div>
      {resource.loading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorMessage error={resource.error} retry={resource.reload} />
      ) : rows.length ? (
        <div className="budget-grid">
          {rows.map((budget) => (
            <BudgetCard
              key={budget.id}
              budget={budget}
              onView={() => setDetails(budget)}
              onEdit={() => setEdit(budget)}
              onDelete={() => {
                setDeleting(budget);
                setError("");
              }}
            />
          ))}
        </div>
      ) : (
        <section className="card">
          <Empty title="Give this month a plan">
            Create your first category budget for {monthLabel(period)}.
          </Empty>
        </section>
      )}
      <p className="page-note">
        Budget progress includes PKR expenses in the matching category. Other
        currencies stay separate.
      </p>
      {details && <BudgetDetails budget={details} onClose={() => setDetails(null)}/>}
      {edit && (
        <Modal
          title={
            edit === "new"
              ? "Create a monthly budget"
              : `Edit ${edit.category} budget`
          }
          onClose={() => setEdit(null)}
          busy={busy}
        >
          <BudgetForm
            initial={edit === "new" ? undefined : edit}
            period={period}
            onBusy={setBusy}
            onSaved={savedPeriod => {
              setPeriod(savedPeriod);
              setEdit(null);
              resource.reload();
              toast("Budget saved.");
            }}
          />
        </Modal>
      )}
      {deleting && (
        <Modal
          title="Delete this budget?"
          onClose={() => setDeleting(null)}
          busy={busy}
        >
          <p>
            The {deleting.category} budget will be removed. Recorded expenses
            will stay in your account.
          </p>
          <ErrorMessage error={error} />
          <div className="modal-actions">
            <Button
              variant="secondary"
              onClick={() => setDeleting(null)}
              disabled={busy}
            >
              Keep budget
            </Button>
            <Button variant="danger" busy={busy} onClick={remove}>
              Delete budget
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}
