import { expect, test, type Browser, type Page } from "@playwright/test";

const CRISIS = /Tele-MANAS on 14416/;

async function demoLogin(browser: Browser, role: "Client" | "Therapist"): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto("/login");
  await expect(page.getByRole("note")).toHaveText("Demo: use fictional information only.");
  await page.getByRole("button", { name: role, exact: true }).click();
  await expect(page).toHaveURL(role === "Client" ? /\/client$/ : /\/therapist$/);
  return page;
}

// Beta (client2) is the other client of the same therapist; the canned copilot output cites the knowledge entries
// retrieved for each client, and only Beta's entries have a library exercise to release.
async function passwordLogin(browser: Browser, email: string, password: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/client$/);
  return page;
}

test("demo path with FAKE_LLM=1", async ({ browser }) => {
  const therapist = await demoLogin(browser, "Therapist");
  const client = await demoLogin(browser, "Client"); // Alpha: books, plateau
  const beta = await passwordLogin(browser, "client2@example.com", "client123"); // Beta: exercise

  // therapist opens a slot for the client to book (no availability UI in the spec)
  const start = new Date(Date.now() + 2 * 3600_000 + 17_000);
  const slot = await therapist.request.post("/api/therapists/me/availability", {
    data: { starts_at: start.toISOString(), ends_at: new Date(start.getTime() + 50 * 60_000).toISOString() },
  });
  expect(slot.ok()).toBeTruthy();

  // 1. client browses and books
  const exercisesBefore = await beta.getByRole("link", { name: "Open" }).count();
  await client.goto("/");
  await client.getByRole("link", { name: /Demo Calm Minds Practice/ }).click();
  await expect(client).toHaveURL(/\/p\/demo-calm-minds$/);
  await client.locator("div", { hasText: /^Dr Demo Therapist One/ }).getByRole("link", { name: "Book a session" }).first().click();
  await client.getByRole("button", { name: "Select" }).first().click();
  await client.getByRole("button", { name: /^Confirm/ }).click();
  await expect(client.getByRole("heading", { name: "Booking confirmed" })).toBeVisible();
  await client.getByRole("link", { name: "Fill in intake form" }).click();
  await client.getByLabel("What brings you here?").fill("Evenings are hard; my mind is busy at night.");
  await client.getByRole("button", { name: "Submit" }).click();
  await expect(client.getByText("Intake saved. Thank you.")).toBeVisible();

  // 2. therapist: Prepare my day -> briefing with INFERRED badge -> approve exercise
  await therapist.goto("/therapist");
  await therapist.getByRole("button", { name: "Prepare my day" }).click();
  await expect(therapist.getByText(/^Briefed \d+ client/)).toBeVisible();
  await expect(therapist.getByRole("status").filter({ hasText: "Briefed" })).toHaveCount(1);
  await expect(therapist.getByText("INFERRED").first()).toBeVisible();
  await therapist.getByRole("link", { name: "Approval inbox" }).click();
  const exercise = therapist.locator("div.shadow-sm", { hasText: /Release exercise to client[\s\S]*For Client Beta Demo/ }).filter({ has: therapist.getByRole("button", { name: "Approve" }) }).first();
  await expect(exercise).toBeVisible();
  await expect(exercise).toContainText("What reaches the client");
  await exercise.getByRole("button", { name: "Approve" }).click();
  await expect(therapist.getByText(/Decided \(\d+\)/)).toBeVisible();

  // 3. client sees it
  await beta.goto("/client");
  await expect(beta.getByRole("link", { name: "Open" })).toHaveCount(exercisesBefore + 1);

  // 4. overnight check -> plateau alert -> acknowledge
  await therapist.goto("/therapist");
  await therapist.getByRole("button", { name: "Run overnight check now" }).click();
  await expect(therapist.getByRole("status").filter({ hasText: "Checked" })).toContainText("plateau");
  const plateau = therapist.getByRole("listitem").filter({ hasText: "no meaningful PHQ-9/GAD-7 improvement" });
  await expect(plateau).toBeVisible();
  await plateau.getByRole("button", { name: "Acknowledge" }).click();
  await expect(plateau.getByText(/^Acknowledged/)).toBeVisible();

  // 5. plan update: diff shown, then approved
  await therapist.getByRole("link", { name: "Approval inbox" }).click();
  const plan = therapist.locator("div.shadow-sm", { hasText: /Update case plan[\s\S]*For Client Alpha Demo/ }).filter({ has: therapist.getByRole("button", { name: "Approve" }) }).first();
  const changes = plan.getByLabel("What changes");
  await expect(changes).toBeVisible();
  await expect(changes).toContainText("Before (current version)");
  await expect(changes).toContainText("After (new version)");
  await expect(changes).toContainText("Reduce racing thoughts at bedtime");
  await expect(changes).toContainText("Changed: formulation");
  await plan.getByRole("button", { name: "Approve" }).click();
  await expect(therapist.locator("div.shadow-sm", { hasText: /Update case plan/ }).filter({ has: therapist.getByRole("button", { name: "Approve" }) })).toHaveCount(0);
  await therapist.reload();
  await expect(therapist.getByText(/Decided \(\d+\)/)).toBeVisible();

  // 6. risky phrase in a check-in: only the fixed crisis message
  await beta.goto("/client");
  await beta.getByRole("link", { name: "Open" }).first().click();
  await expect(beta.getByRole("button", { name: "Save check-in" })).toBeVisible();
  for (const box of await beta.locator("textarea").all()) await box.fill("I want to end my life");
  for (const num of await beta.locator("input[type=number]").all()) await num.fill("5");
  await beta.getByRole("button", { name: "Save check-in" }).click();
  const alert = beta.getByRole("alert");
  await expect(alert).toHaveText(/^You are not alone/);
  await expect(alert).toContainText(CRISIS);
  await expect(beta.getByText("Check-in saved.")).toHaveCount(0);
  await expect(beta.getByRole("button", { name: "Save check-in" })).toHaveCount(0);
  await expect(beta.getByText("I want to end my life")).toHaveCount(0);

  // therapist is alerted (risk section, pinned)
  await therapist.goto("/therapist");
  await expect(therapist.getByRole("region", { name: "Risk alerts" })).toContainText("risk alert");
});
