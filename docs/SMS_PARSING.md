# Wallet and bank SMS parsing

`POST /expenses/parse-sms` accepts manually pasted SMS text. It uses the existing expense router and the same authenticated `get_expense_parser` provider as natural-language extraction. The service classifies the SMS and checks the amount, currency, status, and date locally. For an eligible transaction, the existing Gemini adapter enriches the draft from a redacted copy of the message. Pydantic validates the structured enrichment and the final response. The route has no database dependency.

## Classification and eligibility

| Transaction | Behavior |
| --- | --- |
| Completed debit, merchant payment, bill payment, mobile top-up, or wallet payment | Expense candidate. A generic debit still needs a purpose before it has a usable category. |
| Credit, salary deposit, or incoming transfer | Notification metadata with an empty expense draft. |
| ATM withdrawal or own-account transfer | Movement of funds with an empty expense draft. |
| Outgoing transfer with an unclear purpose | Requires clarification and carries an empty expense draft. |
| Failed, reversed, pending, or unconfirmed payment | Ineligible even when the message includes an amount. An unknown completion status on a potential expense requires clarification. |
| Balance notice or non-financial message | Returns a classification and an empty expense draft. An unclear financial message can request clarification. |

The statuses are `completed`, `failed`, `reversed`, `pending`, and `unknown`. Completion requires textual evidence. Failure, reversal, and pending cues take precedence over words such as “debited” or “paid.” A message with contradictory debit and credit cues requires review. This parser processes one notification at a time.

The test suite includes synthetic Easypaisa, JazzCash, HBL, UBL, Meezan Bank, Bank Alfalah, Allied Bank, and generic banking messages. The rules use transaction language across sources. `source` is a label inferred from the text and carries no sender verification.

## Amounts, dates, and metadata

The parser recognizes currency-marked amounts such as `Rs. 1,500`, `PKR 1500.00`, `1500 rupees`, `Rs 2,500/-`, and `1,250.75 PKR`. It also accepts a number after an explicit `Amount:` label, leaving the currency unknown if the SMS gives none. The service uses `Decimal` and returns money as JSON strings. It excludes amounts labeled as balances, fees, charges, or reference numbers. If more than one plausible transaction amount remains, or an amount is malformed or non-positive, the expense amount stays null and the result requires clarification.

The currency allowlist is shared with the natural-language parser. Local rupee cues map to PKR. Ambiguous currency symbols remain unknown. A recognized currency code outside the allowlist returns `422`.

The parser understands `10-Nov-2026`, `2026-11-10`, `Nov 10, 2026`, and unambiguous slash dates such as `13/11/2026`. A date such as `10/11/2026` has two possible interpretations, so the date stays null and the result requires clarification. The service treats explicit dates as Asia/Karachi calendar dates. It uses an injectable reference datetime for explicit `today` or `yesterday` wording. Absent or invalid dates stay null.

Gemini can suggest a configured category when it cites a purpose from the message. Merchant, description, and payment method must come from text in the redacted message. Unknown values stay null. A transaction reference is optional and stays separate from Expense CRUD fields. Repeated pastes return the same locally derived facts. Provider suggestions may vary between requests. Persistent duplicate detection would require an approved reference field or separate import record scoped to the user and source. This phase does not create either.

## API and confirmation

Example request body

```json
{
  "text": "JazzCash: PKR 1,250.75 wallet payment completed at Fresh Mart on 10-Nov-2026. Ref: TX12345."
}
```

Example response

```json
{
  "extracted_fields": {
    "amount": "1250.75",
    "currency": "PKR",
    "transaction_date": "2026-11-10",
    "category": "Groceries",
    "description": "Fresh Mart",
    "payment_method": "wallet"
  },
  "missing_fields": [],
  "confirmation_required": true,
  "transaction_type": "wallet_payment",
  "transaction_status": "completed",
  "amount": "1250.75",
  "currency": "PKR",
  "transaction_date": "2026-11-10",
  "merchant": "Fresh Mart",
  "transaction_reference": "TX12345",
  "source": "JazzCash",
  "is_expense_candidate": true,
  "clarification_required": false
}
```

The [shared contract](BACKEND_CONTRACT.md#request-and-response-schemas) marks the additive response fields as pending approval. The inherited `confirmation_required` field remains `true` for compatibility. Clients check `is_expense_candidate` first. If it is false, they display the transaction classification without offering to save a draft. If it is true and `clarification_required` is true, the user must review and fill in the unresolved fields. After the user explicitly confirms, the client submits just the reviewed Expense fields to the existing authenticated `POST /expenses` endpoint.

| HTTP status | Meaning |
| --- | --- |
| `200` | An expense draft, a non-expense classification, or a result requiring clarification. |
| `401` | The shared authentication dependency rejected the request. |
| `422` | Invalid or blank text, text longer than 2,000 characters after trimming, or unsupported currency. |
| `502` | The provider returned invalid structured enrichment. |
| `503` | The shared parser or Gemini is unavailable, including exhausted provider rate limits. |
| `504` | Gemini timed out. |

## Privacy and integration

The service sends only the redacted SMS text needed for eligible drafts. It masks recognized references and labeled identifiers, authentication codes, numbers, and web links. This reduces exposure and can hide digits in merchant names. Remaining text may still identify the sender, merchant, or account holder. The service does not store raw messages, log bodies, or send account data from the authenticated user. The fixed system instruction treats message content as untrusted, and the existing SDK adapter offers no tools. Structured output cannot set the amount, classification, date, or user ID. The returned transaction reference should be handled as sensitive metadata by the client.

Reuse the single app-lifespan `ExpenseAIService` and Gemini client configured for [natural-language parsing](AI_EXPENSE_PARSING.md#integration-and-tests). Developer 1 should bind `get_expense_parser` to the real JWT dependency and mount the existing expense router once. The SMS and natural-language routes then share the same key, model, timeouts, retries, and category and currency configuration. Confirm the proposed response fields, eligibility rules, privacy policy for Gemini transmission, and any future reference storage before deployment.

With the [existing backend and SDK dependencies](AI_EXPENSE_PARSING.md#integration-and-tests), run `python -m unittest discover -s backend/tests -v`. SMS tests use synthetic fixtures and the real SDK with a mocked HTTP transport. Production JWT wiring and a live Gemini request remain integration checks.
