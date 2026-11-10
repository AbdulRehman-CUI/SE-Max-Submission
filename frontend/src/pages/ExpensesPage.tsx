import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Plus, Search, SlidersHorizontal } from "lucide-react";
import { expenses } from "../api";
import { ExpenseForm } from "../components/ExpenseForm";
import { ExpenseTable } from "../components/Finance";
import {
  Button,
  ErrorMessage,
  Field,
  Loading,
  Modal,
  PageHeading,
  useToast,
} from "../components/ui";
import { useResource } from "../hooks/useResource";
import { cents, message } from "../lib/format";
import type { Expense } from "../types/api";
export default function ExpensesPage() {
  const resource = useResource(expenses.list);
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<Expense | "new" | null>(null);
  const edit = selected ?? (params.has("new") ? "new" : null);
  function setEdit(value: Expense | "new" | null) {
    setSelected(value);
    if (params.has("new")) setParams({}, { replace: true });
  }
  const [deleting, setDeleting] = useState<Expense | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [month, setMonth] = useState("");
  const [sort, setSort] = useState("date-desc");
  const rows = (resource.data || [])
    .filter(
      (row) =>
        (!category || row.category === category) &&
        (!month || row.transaction_date.startsWith(month)) &&
        `${row.description || ""} ${row.category} ${row.payment_method || ""}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    )
    .sort((a, b) => {
      const comparison = sort.startsWith("amount")
        ? cents(a.amount) < cents(b.amount)
          ? -1
          : cents(a.amount) > cents(b.amount)
            ? 1
            : 0
        : a.transaction_date.localeCompare(b.transaction_date);
      return sort.endsWith("desc") ? -comparison : comparison;
    });
  async function remove() {
    if (!deleting) return;
    setBusy(true);
    setError("");
    try {
      await expenses.remove(deleting.id);
      setDeleting(null);
      resource.reload();
      toast("Expense deleted.");
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="YOUR EVERYDAY, ACCOUNTED FOR"
        title="Expenses"
        description="A clear view of where your money goes."
      >
        <Button onClick={() => setEdit("new")}>
          <Plus size={18} />
          Add expense
        </Button>
      </PageHeading>
      <section className="card">
        <div className="filter-bar">
          <label className="search-box">
            <Search size={17} />
            <span className="sr-only">Search expenses</span>
            <input
              placeholder="Search transactions…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <Field label="Category">
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="">All categories</option>
              {[...new Set(resource.data?.map((row) => row.category))]
                .sort()
                .map((item) => (
                  <option key={item}>{item}</option>
                ))}
            </select>
          </Field>
          <Field label="Month">
            <input
              type="month"
              value={month}
              onChange={(event) => setMonth(event.target.value)}
            />
          </Field>
          <Field label="Sort by">
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value)}
            >
              <option value="date-desc">Newest first</option>
              <option value="date-asc">Oldest first</option>
              <option value="amount-desc">Amount: high to low</option>
              <option value="amount-asc">Amount: low to high</option>
            </select>
          </Field>
        </div>
        <div className="table-meta">
          <span>{rows.length} transactions</span>
          <Button
            variant="ghost"
            onClick={() => {
              setQuery("");
              setCategory("");
              setMonth("");
            }}
          >
            <SlidersHorizontal size={14} />
            Clear filters
          </Button>
        </div>
        {resource.loading ? (
          <Loading />
        ) : resource.error ? (
          <ErrorMessage error={resource.error} retry={resource.reload} />
        ) : (
          <ExpenseTable
            rows={rows}
            onEdit={setEdit}
            onDelete={(row) => {
              setDeleting(row);
              setError("");
            }}
          />
        )}
      </section>
      {edit && (
        <Modal
          title={edit === "new" ? "Add an expense" : "Edit expense"}
          onClose={() => setEdit(null)}
          busy={busy}
        >
          <ExpenseForm
            initial={edit === "new" ? undefined : edit}
            onSave={async (value) => {
              setBusy(true);
              try {
                if (edit === "new") await expenses.create(value);
                else await expenses.update(edit.id, value);
                setEdit(null);
                resource.reload();
                toast("Expense saved.");
              } finally {
                setBusy(false);
              }
            }}
          />
        </Modal>
      )}
      {deleting && (
        <Modal
          title="Delete this expense?"
          onClose={() => setDeleting(null)}
          busy={busy}
        >
          <p>
            This removes “{deleting.description || deleting.category}” and
            updates your spending and budget totals. This cannot be undone.
          </p>
          <ErrorMessage error={error} />
          <div className="modal-actions">
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setDeleting(null)}
            >
              Keep expense
            </Button>
            <Button variant="danger" busy={busy} onClick={remove}>
              Delete expense
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}
