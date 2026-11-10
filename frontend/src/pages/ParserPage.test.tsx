import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import ParserPage from "./ParserPage";

describe("parser review", () => {
  it("requires review and sends only the explicitly confirmed, edited decimal expense", async () => {
    const user = userEvent.setup();
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          confirmation_required: true,
          missing_fields: ["category"],
          extracted_fields: {
            amount: "850.00",
            currency: "PKR",
            transaction_date: "2026-11-10",
          },
        }),
      )
      .mockResolvedValueOnce(Response.json({ id: "test" }, { status: 201 }));
    vi.stubGlobal("fetch", fetcher);
    render(
      <MemoryRouter>
        <ParserPage />
      </MemoryRouter>,
    );
    await user.click(
      screen.getByRole("button", {
        name: "I spent 850 rupees on lunch today.",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Parse expense" }));
    const save = await screen.findByRole("button", { name: "Confirm & save" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(save).toBeDisabled();
    await user.type(screen.getByLabelText("Category"), "Food");
    await user.clear(screen.getByLabelText("Amount"));
    await user.type(screen.getByLabelText("Amount"), "860.05");
    await user.click(screen.getByRole("checkbox"));
    await user.click(save);
    expect(await screen.findByText("Expense saved.")).toBeVisible();
    expect(fetcher.mock.calls[1][0]).toMatch(/\/expenses$/);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({
      amount: "860.05",
      category: "Food",
      description: null,
      transaction_date: "2026-11-10",
      currency: "PKR",
      payment_method: null,
    });
  });

  it("shows an ineligible SMS classification and offers no save action", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn().mockResolvedValue(
      Response.json({
        confirmation_required: true,
        extracted_fields: {},
        missing_fields: [],
        transaction_type: "balance_notification",
        transaction_status: "unknown",
        amount: null,
        currency: "PKR",
        transaction_date: null,
        is_expense_candidate: false,
        clarification_required: false,
      }),
    );
    vi.stubGlobal("fetch", fetcher);
    render(
      <MemoryRouter>
        <ParserPage sms />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: "Other bank" }));
    await user.click(screen.getByRole("button", { name: "Parse SMS" }));
    expect(await screen.findByText("balance notification")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Confirm & save" })).toBeNull();
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toMatch(/\/expenses\/parse-sms$/);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
