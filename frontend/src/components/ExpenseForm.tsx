import { useState, type FormEvent } from "react";
import type { ExpenseInput, ParseResult } from "../types/api";
import { message, today, validMoney } from "../lib/format";
import { Button, ErrorMessage, Field } from "./ui";
export function ExpenseForm({
  initial,
  onSave,
  label = "Save expense",
  requireReview = false,
}: {
  initial?: ParseResult["extracted_fields"];
  onSave: (value: ExpenseInput) => Promise<void>;
  label?: string;
  requireReview?: boolean;
}) {
  const [value, setValue] = useState<ExpenseInput>({
    amount: initial?.amount ?? "",
    category: initial?.category ?? "",
    description: initial?.description ?? "",
    transaction_date: initial ? (initial.transaction_date ?? "") : today(),
    currency: initial?.currency ?? "PKR",
    payment_method: initial?.payment_method ?? "",
  });
  const [reviewed, setReviewed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  function field(key: keyof ExpenseInput, input: string) {
    setValue((previous) => ({ ...previous, [key]: input }));
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!validMoney(value.amount)) {
      setError(
        "Enter a positive amount with up to 10 whole digits and 2 decimal places.",
      );
      return;
    }
    if (!value.category.trim()) {
      setError("Enter a category.");
      return;
    }
    if (requireReview && !reviewed) return;
    setBusy(true);
    setError("");
    try {
      await onSave({
        ...value,
        category: value.category.trim(),
        description: value.description?.trim() || null,
        payment_method: value.payment_method?.trim() || null,
        currency: value.currency.toUpperCase(),
      });
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="form-stack">
      <ErrorMessage error={error} />
      <fieldset disabled={busy}>
        <div className="form-grid">
          <Field label="Amount">
            <input
              autoFocus
              inputMode="decimal"
              required
              placeholder="0.00"
              maxLength={13}
              value={value.amount}
              onChange={(event) => field("amount", event.target.value)}
            />
          </Field>
          <Field label="Currency">
            <input
              required
              pattern="[A-Za-z]{3}"
              maxLength={3}
              value={value.currency}
              onChange={(event) =>
                field("currency", event.target.value.toUpperCase())
              }
            />
          </Field>
          <Field label="Category">
            <input
              required
              maxLength={100}
              placeholder="e.g. Food"
              list="expense-categories"
              value={value.category}
              onChange={(event) => field("category", event.target.value)}
            />
          </Field>
          <datalist id="expense-categories">
            {[
              "Food",
              "Transport",
              "Shopping",
              "Bills",
              "Health",
              "Education",
              "Entertainment",
              "Other",
            ].map((item) => (
              <option key={item}>{item}</option>
            ))}
          </datalist>
          <Field label="Transaction date">
            <input
              type="date"
              required
              min="0001-01-01"
              max="9999-12-31"
              value={value.transaction_date}
              onChange={(event) =>
                field("transaction_date", event.target.value)
              }
            />
          </Field>
        </div>
        <Field label="Description (optional)">
          <textarea
            rows={2}
            maxLength={255}
            placeholder="What was it for?"
            value={value.description ?? ""}
            onChange={(event) => field("description", event.target.value)}
          />
        </Field>
        <Field label="Payment method (optional)">
          <input
            maxLength={50}
            placeholder="e.g. Cash, card, Easypaisa"
            value={value.payment_method ?? ""}
            onChange={(event) => field("payment_method", event.target.value)}
          />
        </Field>
        {requireReview && (
          <label className="check-field">
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(event) => setReviewed(event.target.checked)}
              required
            />
            <span>
              I checked the amount, date and classification and resolved any
              uncertainty. This is an expense I want to record.
            </span>
          </label>
        )}
        <Button type="submit" busy={busy} disabled={requireReview && !reviewed}>
          {label}
        </Button>
      </fieldset>
    </form>
  );
}
