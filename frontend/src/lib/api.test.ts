import { describe, expect, it, vi } from "vitest";
import {
  allPages,
  json,
  normalizeApiBase,
  request,
  session,
} from "./api";

describe("API client", () => {
  it("normalizes production and local API bases without duplicate prefixes", () => {
    expect(
      normalizeApiBase("https://se-max-submission-backend.vercel.app/"),
    ).toBe("https://se-max-submission-backend.vercel.app");
    expect(
      normalizeApiBase("https://se-max-submission-backend.vercel.app/api/"),
    ).toBe("https://se-max-submission-backend.vercel.app");
    expect(normalizeApiBase("/api/")).toBe("/api");
  });

  it("sends JSON with bearer authentication and accepts an empty response", async () => {
    session.set("synthetic-token");
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetcher);
    await expect(
      request("/expenses/example", json("PATCH", { amount: "125.05" })),
    ).resolves.toBeUndefined();
    expect(fetcher.mock.calls[0][0]).toMatch(/\/expenses\/example$/);
    const options = fetcher.mock.calls[0][1];
    expect(options.headers.get("Authorization")).toBe("Bearer synthetic-token");
    expect(options.headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual({ amount: "125.05" });
  });

  it("clears an expired session and emits the sign-out event", async () => {
    session.set("synthetic-token");
    const unauthorized = vi.fn();
    window.addEventListener("spendsense:unauthorized", unauthorized, {
      once: true,
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json({ detail: "internal data" }, { status: 401 }),
        ),
    );
    await expect(request("/auth/me")).rejects.toMatchObject({
      status: 401,
      message: expect.stringContaining("sign in"),
    });
    expect(session.get()).toBeNull();
    expect(unauthorized).toHaveBeenCalledOnce();
  });

  it("explains validation without exposing submitted values or server internals", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            {
              detail: [
                { loc: ["body", "transaction_date"], input: "private data" },
              ],
            },
            { status: 422 },
          ),
        ),
    );
    await expect(request("/expenses")).rejects.toThrow(
      "Please check transaction date and try again.",
    );
  });

  it("continues past a full page so local filters cover all expenses", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json(Array.from({ length: 100 }, (_, i) => i)),
      )
      .mockResolvedValueOnce(Response.json([100]));
    vi.stubGlobal("fetch", fetcher);
    expect(await allPages("/expenses")).toHaveLength(101);
    expect(fetcher.mock.calls[1][0]).toMatch(/skip=100&limit=100$/);
  });
});
