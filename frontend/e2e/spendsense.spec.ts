import { expect, test } from "@playwright/test";

test("public landing works from 320px to wide desktop and honors reduced motion", async ({
  page,
}) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto("/");
  const heading = page.getByRole("heading", { name: "SpendSense." });
  await expect(heading).toHaveCSS("opacity", "1");
  await expect(page.getByText("ILLUSTRATIVE PREVIEW")).toBeVisible();
  await page.evaluate(() => window.scrollTo({ top: 350, behavior: "instant" }));
  await expect
    .poll(() =>
      page
        .locator(".orb-one")
        .evaluate((element) => getComputedStyle(element).transform),
    )
    .not.toBe("none");
  for (const width of [320, 390, 768, 1024, 1536]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBe(width);
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await expect(heading).toHaveCSS("opacity", "1");
  await expect(page.locator(".orb-one")).toHaveCSS("transform", "none");
  expect(pageErrors).toEqual([]);
});

test("visiting a protected route while signed out redirects to login", async ({
  page,
}) => {
  await page.goto("/expenses");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Email or username")).toBeVisible();
});

test("merged FastAPI and PostgreSQL support the complete signed-in finance flow", async ({
  page,
}) => {
  test.skip(
    process.env.SPENDSENSE_E2E_LIVE !== "1",
    "Enable against a disposable backend using SPENDSENSE_E2E_LIVE=1.",
  );
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  const openapi = await page.request.get("/api/openapi.json");
  expect(openapi.ok()).toBe(true);
  const { paths } = await openapi.json();
  for (const [path, method] of [
    ["/auth/login", "post"],
    ["/auth/register", "post"],
    ["/auth/me", "get"],
    ["/expenses", "get"],
    ["/expenses", "post"],
    ["/expenses/{expense_id}", "patch"],
    ["/expenses/{expense_id}", "delete"],
    ["/budgets", "get"],
    ["/budgets", "post"],
    ["/budgets/{budget_id}", "patch"],
    ["/budgets/{budget_id}", "delete"],
    ["/budgets/{budget_id}/summary", "get"],
    ["/analytics/summary", "get"],
    ["/v2/analytics/monthly", "get"],
    ["/v2/analytics/trends", "get"],
    ["/v2/analytics/anomalies/check", "post"],
    ["/v2/analytics/insights", "get"],
    ["/expenses/parse", "post"],
    ["/expenses/parse-sms", "post"],
  ])
    expect(paths[path][method]).toBeTruthy();

  const username = `browser_${Date.now()}`;
  await page.goto("/register");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Email address").fill(`${username}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("test-only-spendsense-password");
  await page
    .getByLabel("Confirm password")
    .fill("test-only-spendsense-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("No category spending")).toBeVisible();
  await expect(
    page.getByText("Insights based on your spending statistics"),
  ).toBeVisible();
  await page.getByRole("link", { name: "Add expense" }).click();
  await page.getByLabel("Amount", { exact: true }).fill("1250.05");
  await page
    .getByRole("dialog")
    .getByLabel("Category", { exact: true })
    .fill("Food");
  await page.getByLabel("Description (optional)").fill("Browser lunch");
  await page.getByRole("button", { name: "Save expense" }).click();
  await expect(page.getByRole("row", { name: /Browser lunch/ })).toContainText(
    "PKR 1,250.05",
  );
  await page.getByRole("button", { name: "Edit Browser lunch" }).click();
  await page.getByLabel("Amount", { exact: true }).fill("1300.10");
  await page.getByRole("button", { name: "Save expense" }).click();
  await expect(page.getByRole("row", { name: /Browser lunch/ })).toContainText(
    "PKR 1,300.10",
  );

  await page.getByRole("link", { name: "Budgets", exact: true }).click();
  await page.getByRole("button", { name: "Create budget" }).click();
  await page.getByLabel("Category", { exact: true }).fill("Food");
  await page.getByLabel("Monthly limit (PKR)").fill("1000.00");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Create budget" })
    .click();
  await expect(page.getByText("Over budget", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Edit Food budget" }).click();
  await page.getByLabel("Monthly limit (PKR)").fill("1500.00");
  await page.getByRole("button", { name: "Update budget" }).click();
  await expect(page.getByText("PKR 199.90 remaining")).toBeVisible();
  await page.getByRole("button", { name: "View Food budget summary" }).click();
  await expect(page.getByRole("dialog")).toContainText("PKR 199.90 remaining");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.getByRole("link", { name: "Analytics", exact: true }).click();
  await expect(
    page.getByText("Month in progress", { exact: false }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: /Monthly spending in PKR/ }),
  ).toBeVisible();
  await page
    .getByLabel("Transaction", { exact: true })
    .selectOption({
      label: await page
        .getByLabel("Transaction", { exact: true })
        .locator("option")
        .nth(1)
        .innerText(),
    });
  await page.getByRole("button", { name: "Check transaction" }).click();
  await expect(page.getByText(/Insufficient history · Food/)).toBeVisible();
  await page.getByRole("link", { name: "Insights", exact: true }).click();
  await expect(
    page.getByText("Insights based on your spending statistics"),
  ).toBeVisible();

  await page.setViewportSize({ width: 320, height: 780 });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "Expenses", exact: true })
    .click();
  await expect(page.getByRole("row", { name: /Browser lunch/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
  await page.reload();
  await expect(page.getByRole("row", { name: /Browser lunch/ })).toBeVisible();
  await page.getByRole("button", { name: "Delete Browser lunch" }).click();
  await page
    .getByRole("button", { name: "Delete expense", exact: true })
    .click();
  await expect(page.getByText("No expenses here yet")).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "Budgets", exact: true })
    .click();
  await expect(page.getByText("PKR 1,500.00 remaining")).toBeVisible();
  await page.getByRole("button", { name: "Delete Food budget" }).click();
  await page
    .getByRole("button", { name: "Delete budget", exact: true })
    .click();
  await expect(page.getByText("Give this month a plan")).toBeVisible();

  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "AI Assistant" })
    .click();
  await page
    .getByRole("button", { name: "I spent 850 rupees on lunch today." })
    .click();
  const parse = page.waitForResponse((response) =>
    response.url().endsWith("/expenses/parse"),
  );
  await page.getByRole("button", { name: "Parse expense" }).click();
  expect((await parse).status()).toBe(503);
  await expect(page.getByRole("alert")).toContainText(
    "temporarily unavailable",
  );

  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("dialog").getByRole("link", { name: "SMS Parser" }).click();
  await page.getByRole("button", { name: "Other bank", exact: true }).click();
  const sms = page.waitForResponse(response => response.url().endsWith("/expenses/parse-sms"));
  await page.getByRole("button", { name: "Parse SMS" }).click();
  expect((await sms).status()).toBe(503);
  await expect(page.getByRole("alert")).toContainText("temporarily unavailable");

  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "Settings" })
    .click();
  await expect(page.getByText("Asia/Karachi", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email or username").fill(username);
  await page
    .getByLabel("Password", { exact: true })
    .fill("test-only-spendsense-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: `Hello, ${username}.` })).toBeVisible();
  expect(pageErrors).toEqual([]);
});
