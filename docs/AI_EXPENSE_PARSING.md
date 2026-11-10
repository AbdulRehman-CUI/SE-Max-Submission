# Natural-language expense parsing

`POST /expenses/parse` takes `ExpenseParseRequest.text` and returns the existing `ExpenseParseResponse`. The route uses Developer 1's JWT dependency through `get_expense_parser`. `ExpenseAIService` calls an extraction provider, validates the result, and builds the draft. `GeminiExpenseProvider` wraps the official async Google Gen AI SDK. Parsing has no database dependency.

## Configuration

| Environment variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Server-side Gemini credential. Required when creating an SDK client from the environment. |
| `GEMINI_MODEL` | Model override for `GeminiExpenseProvider.from_env()`. Defaults to the stable `gemini-3.8-flash`, which supports structured output. |

Set environment variables through the app's deployment or configuration system. `from_env()` reads the process environment. It does not load `.env` files. Use the SDK adapter with an injected async client when Developer 1 supplies a shared client and model. [Google Gen AI SDK](https://googleapis.github.io/python-genai/), [Gemini 3.8 Flash model reference](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash?authuser=3)

## Draft contract and confirmation

Example request body

```json
{"text": "Aaj khanay pe 500.00 rupay lagay."}
```

Example response when the local date is November 10, 2026

```json
{
  "extracted_fields": {
    "amount": "500.00",
    "category": "Food",
    "description": "khanay",
    "transaction_date": "2026-11-10",
    "currency": "PKR",
    "payment_method": null
  },
  "missing_fields": [],
  "confirmation_required": true
}
```

The SDK requests structured JSON with the server's output schema. Its internal result has the expense fields plus a single/multiple/none classification, a relative date marker, and a literal currency cue. The service rejects unexpected fields, then validates the draft through the existing Pydantic schema. Amounts use `Decimal`, and JSON serializes them as strings. A missing amount, category, or date appears in `missing_fields`. Unknown currency and payment method remain null. A message containing multiple distinct expenses returns `422` so the caller can split it.

The client displays the draft, lets the user correct or fill in fields, and asks for explicit confirmation. On confirmation it submits a separate `POST /expenses` request using `ExpenseCreate`. The existing authenticated CRUD service determines ownership and persists the expense. The draft has no persistence ID and needs no storage or cleanup.

## Language, dates, and categories

The extraction instruction supports English, Roman Urdu, and mixed text. It recognizes items such as `khanay` for a food expense, `kiraya` for transport fare, and `bijli ka bill` for a utility bill. The backend verifies a non-null amount against a numeric literal in the message and preserves the source's decimal precision. Word-only amounts stay null so the user can supply a number. Description and payment method must come from text the user supplied.

The service converts an aware reference datetime to `Asia/Karachi`. The model interprets the language and returns a relative marker or an explicit calendar date. The backend computes today, yesterday, the day before yesterday, future markers, and the previous occurrence of a named weekday. `aaj` and `aj` map to today. `kal` and `parson` need enough past or future context to choose a marker, and ambiguity leaves the date missing. An omitted date also stays missing. Tests inject an aware reference datetime to cover the UTC-to-Karachi day boundary.

**Proposed, pending team approval.** Category suggestions are Food, Groceries, Transport, Shopping, Bills, Education, Health, Entertainment, and Other. The application can supply its own category list to `ExpenseAIService`. The model chooses from that list or leaves an ambiguous category null. The service normalizes capitalization to the configured label.

**Proposed, pending team approval.** The default parsing currency allowlist is PKR, USD, EUR, GBP, INR, AED, and SAR. The application can override it. The service accepts the literal currency code or a recognized cue. Local cues such as `Rs.`, `rupees`, and `rupay` can identify PKR when the surrounding context supports that interpretation. A bare amount or ambiguous cue such as `$` remains null in the draft. The existing `ExpenseCreate` schema supplies the PKR default when the user confirms a create request without a currency.

## Failure handling and security

| HTTP status | Meaning |
| --- | --- |
| `401` | Developer 1's authentication dependency rejected the request. |
| `422` | Invalid or blank text, text longer than 2,000 characters after trimming, no expense, multiple expenses, or an unsupported currency. |
| `502` | The provider returned missing, malformed, invalid, or ungrounded output. |
| `503` | The parser is unconfigured, Gemini is unavailable, or its rate limit has been reached. Invalid credentials or an unavailable model also map to this status. |
| `504` | The provider timed out. |

The adapter gives each SDK request an eight-second transport timeout and bounds the entire operation to 20 seconds. The SDK has up to three attempts for configured transient HTTP failures, with exponential backoff and jitter. Authentication, model, and output validation failures are returned without retrying. The API returns fixed error details without SDK response bodies or credentials. These parsing statuses are proposed for alignment with Developer 1's shared error format.

The system instruction is server-controlled. The user's message is a separate JSON-encoded data value. The request exposes no tools or function execution. The backend checks the output shape, financial constraints, and literal evidence for amounts, descriptions, payment methods, and currencies. Extraction can still misinterpret language, which is why every successful draft requires review. The service does not log raw messages or credentials. Developer 1 should apply the app's privacy, request-size, and rate-limit policies because the text goes to Gemini.

## Integration and tests

Create one SDK client per application lifespan and reuse it across requests. When there is no shared client, the lifespan can use `async with GeminiExpenseProvider.from_env() as provider` and create `ExpenseAIService(provider)`. For a shared client, pass its async client and the configured model into `GeminiExpenseProvider`. Reuse or relocate this adapter when integrating the shared Gemini client. Leave the default `503` provider in place when Gemini is unconfigured so expense and budget CRUD can still start. Financial insights remain in Developer 1's module.

Register the existing `app.routes.expenses.router` once. Bind `get_expense_parser` to an application provider that depends on the real authenticated-user dependency and returns the lifespan-owned service. The provider needs no database session. For example, with the shared imports and `app.state.expense_parser` initialized during startup:

```python
def provide_expense_parser(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> ExpenseAIService:
    return request.app.state.expense_parser


app.dependency_overrides[get_expense_parser] = provide_expense_parser
```

Confirm the real JWT dependency, SDK client ownership, supported categories and currencies, and error formatting before integration. Phase 5 can reuse the provider boundary once shared configuration is agreed.

Install the existing [backend and test dependencies](EXPENSE_MODULE.md#verification), then install the SDK and IANA time zone data. The latter is needed on Windows hosts without a system IANA database.

```sh
python -m pip install "google-genai>=1.55,<3" tzdata
python -m unittest discover -s backend/tests -v
```

The tests use deterministic provider responses, an HTTP mock transport for the official SDK, and an in-process FastAPI app with an authentication override. No Gemini credentials or database are required. These tests verify the request contract and application behavior. Live extraction quality and access to the configured model require a separate request with team credentials.
