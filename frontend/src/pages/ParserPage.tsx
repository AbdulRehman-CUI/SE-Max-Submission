import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  FileText,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { expenses, parsing } from "../api";
import { ExpenseForm } from "../components/ExpenseForm";
import {
  Button,
  Empty,
  ErrorMessage,
  Field,
  PageHeading,
  useToast,
} from "../components/ui";
import { dateLabel, message, money } from "../lib/format";
import type { ParseResult, SMSResult } from "../types/api";

const phrases = [
  "I spent 850 rupees on lunch today.",
  "Aaj petrol pe 2000 rupay kharch kiye.",
  "Kal university janay ka 150 kiraya diya.",
];
const smsExamples = [
  [
    "Easypaisa",
    "Easypaisa: You paid PKR 450.00 to Green Cafe on 10-Nov-2025. Available balance PKR 5,000.00.",
  ],
  ["JazzCash", "JazzCash: Bill payment of Rs. 1,200 completed on 10-Nov-2025."],
  [
    "HBL",
    "HBL: PKR 790.50 debited for card purchase at Corner Mart on 10-Nov-2025.",
  ],
  ["UBL", "UBL: You received PKR 2,500.00 on 10-Nov-2025."],
  ["Meezan", "Meezan: PKR 1,050.00 paid to City Books on 10-Nov-2025."],
  ["Other bank", "Available balance as of 10-Nov-2025: PKR 22,000.00."],
] as const;

export default function ParserPage({ sms = false }: { sms?: boolean }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<ParseResult | SMSResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const toast = useToast();
  const classification =
    result && "is_expense_candidate" in result ? result : null;
  const eligible =
    result?.confirmation_required === true &&
    (!sms || classification?.is_expense_candidate === true);
  const Icon = sms ? MessageSquareText : Sparkles;
  function change(input: string) {
    setText(input);
    setResult(null);
    setSaved(false);
    setError("");
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) {
      setError("Enter some text to parse.");
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);
    setSaved(false);
    try {
      setResult(
        await (sms ? parsing.sms(text.trim()) : parsing.text(text.trim())),
      );
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow={sms ? "FROM MESSAGE TO RECORD" : "EXPENSE ENTRY, SIMPLIFIED"}
        title={sms ? "Bank & wallet SMS parser" : "AI expense assistant"}
        description={
          sms
            ? "Paste a transaction message and check what it says before recording an expense."
            : "Describe an expense in your own words. Review the details before you save."
        }
      />
      <div className="tool-grid">
        <section className="card tool-card">
          <span className="feature-icon">
            <Icon size={23} />
          </span>
          <h2>{sms ? "Paste a message" : "What did you spend?"}</h2>
          <p className="muted">
            {sms
              ? "You paste the message yourself. SpendSense does not access your inbox or connect to your bank."
              : "English and Roman Urdu are supported. Include the amount and date if you know them."}
          </p>
          <form onSubmit={submit} className="form-stack">
            <ErrorMessage error={error} />
            <Field label={sms ? "Transaction message" : "Expense description"}>
              <textarea
                rows={6}
                required
                maxLength={2000}
                disabled={busy}
                value={text}
                onChange={(event) => change(event.target.value)}
                placeholder={
                  sms
                    ? "Paste your transaction SMS here…"
                    : "I spent 850 rupees on lunch today…"
                }
              />
            </Field>
            <Button type="submit" busy={busy} disabled={!text.trim()}>
              <Icon size={17} />
              {sms ? "Parse SMS" : "Parse expense"}
            </Button>
          </form>
          <p className="example-label">TRY AN EXAMPLE</p>
          <div className="examples">
            {(sms
              ? smsExamples
              : phrases.map((value) => [value, value] as const)
            ).map(([label, example]) => (
              <Button
                variant="secondary"
                key={label}
                disabled={busy}
                onClick={() => change(example)}
              >
                {label}
              </Button>
            ))}
          </div>
          <p className="form-note">
            <ShieldCheck size={17} />
            {sms
              ? "Paste only the transaction details you need. Leave out PINs, passwords and one-time codes."
              : "Parsing creates a draft. Only you can confirm and save it."}
          </p>
        </section>
        <section className="card tool-card" aria-label="Review result">
          <span className="feature-icon">
            <FileText size={23} />
          </span>
          <h2>{sms ? "Transaction review" : "Review your expense"}</h2>
          {saved ? (
            <div className="success-box" role="status">
              Expense saved.{" "}
              <Link className="text-link" to="/expenses">
                View expenses
              </Link>
            </div>
          ) : !result ? (
            <Empty title={busy ? "Reading your text…" : "No draft yet"}>
              Parsed details will appear here for your review.
            </Empty>
          ) : (
            <>
              {classification && (
                <>
                  <dl className="detail-list">
                    <div>
                      <dt>Type</dt>
                      <dd className="capitalize">
                        {classification.transaction_type.replaceAll("_", " ")}
                      </dd>
                    </div>
                    <div>
                      <dt>Status</dt>
                      <dd className="capitalize">
                        {classification.transaction_status}
                      </dd>
                    </div>
                    <div>
                      <dt>Transaction amount</dt>
                      <dd>
                        {classification.amount && classification.currency
                          ? money(
                              classification.amount,
                              classification.currency,
                            )
                          : "Unavailable"}
                      </dd>
                    </div>
                    <div>
                      <dt>Transaction date</dt>
                      <dd>
                        {classification.transaction_date
                          ? dateLabel(classification.transaction_date)
                          : "Unavailable"}
                      </dd>
                    </div>
                    {classification.merchant && (
                      <div>
                        <dt>Merchant</dt>
                        <dd>{classification.merchant}</dd>
                      </div>
                    )}
                    {classification.source && (
                      <div>
                        <dt>Source</dt>
                        <dd>{classification.source}</dd>
                      </div>
                    )}
                  </dl>
                  {!eligible && (
                    <p className="notice">
                      This message was not classified as a recordable expense.
                      Review the transaction type and status above.
                    </p>
                  )}
                  {eligible && classification.clarification_required && (
                    <p className="notice">
                      Some details are uncertain. Verify the amount, date and
                      classification against the original message.
                    </p>
                  )}
                </>
              )}
              {eligible && (
                <>
                  {result.missing_fields.length > 0 && (
                    <p className="notice">
                      Fill in the missing details:{" "}
                      {result.missing_fields
                        .map((field) => field.replaceAll("_", " "))
                        .join(", ")}
                      .
                    </p>
                  )}
                  <ExpenseForm
                    initial={result.extracted_fields}
                    requireReview
                    label="Confirm & save"
                    onSave={async (value) => {
                      await expenses.create(value);
                      setText("");
                      setResult(null);
                      setSaved(true);
                      toast("Expense saved.");
                    }}
                  />
                </>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}
