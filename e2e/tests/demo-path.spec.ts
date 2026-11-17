import { expect, test, type Browser, type Page } from "@playwright/test";

const CRISIS = /Tele-MANAS on 14416/;

async function demoLogin(browser: Browser, role: "Client" | "Therapist"): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto("/login");
  await expect(page.getByRole("contentinfo")).toContainText("Sample data");
  await page.getByRole("button", { name: role, exact: true }).click();
  await expect(page).toHaveURL(role === "Client" ? /\/client$/ : /\/therapist$/);
  return page;
}

test("demo path with FAKE_LLM=1", async ({ browser }) => {
  const therapist = await demoLogin(browser, "Therapist");
  const client = await demoLogin(browser, "Client"); // Alpha: plateau alert -> plan update -> follow-up flag
  const beta = await (await browser.newContext()).newPage(); // Beta: the exercise-release approval
  await beta.goto("/login");
  await beta.getByLabel("Email").fill("client2@example.com");
  await beta.getByLabel("Password").fill("client123");
  await beta.getByRole("button", { name: /^(Sign in|Log in|Login)$/ }).click();
  await expect(beta).toHaveURL(/\/client$/);

  // 0. therapist availability screen: seeded slots are there; add one and remove it again
  await therapist.goto("/therapist/availability");
  await expect(therapist.getByRole("button", { name: /^Remove slot/ }).first()).toBeVisible();
  const extra = new Date(Date.now() + 20 * 86400_000);
  const local = new Date(extra.getTime() - extra.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
  const mine = therapist.getByRole("button", { name: /^Remove slot/ });
  const before = await mine.count();
  await therapist.getByLabel(/New slot starts/).fill(local);
  await therapist.getByRole("button", { name: "Add slot" }).click();
  await expect(mine).toHaveCount(before + 1);
  await mine.last().click(); // furthest slot is the one just added
  await expect(mine).toHaveCount(before);

  // 1. client browses and books a seeded slot
  const exercisesBefore = await beta.getByRole("link", { name: "Open" }).count();
  await client.goto("/directory");
  await client.getByRole("link", { name: /Calm Minds Counselling/ }).first().click();
  await expect(client).toHaveURL(/\/p\/calm-minds-bengaluru$/);
  await client.locator("div.shadow-sm", { hasText: /Dr Meera Krishnan/ }).getByRole("link", { name: "Book a session" }).first().click();
  await client.getByRole("button", { name: "Select" }).first().click();
  await client.getByRole("button", { name: /^Confirm/ }).click();
  await expect(client.getByRole("heading", { name: "Booking confirmed" })).toBeVisible();
  await client.getByRole("link", { name: "Fill in intake form" }).click();
  await client.getByLabel("What brings you here?").fill("Evenings are hard; my mind is busy at night.");
  await client.getByRole("button", { name: "Submit" }).click();
  await expect(client.getByText("Intake saved. Thank you.")).toBeVisible({ timeout: 30_000 }); // first call loads the embedding model

  // 2. therapist: Prepare my day -> briefing with INFERRED badge -> approve Beta's exercise.
  // Alpha already holds open assignments, so Alpha gets no release action.
  await therapist.goto("/therapist");
  await therapist.getByRole("button", { name: "Prepare my day" }).click();
  await expect(therapist.getByText(/^Briefed \d+ client/)).toBeVisible();
  await expect(therapist.getByRole("status").filter({ hasText: "Briefed" })).toHaveCount(1);
  await expect(therapist.getByText("INFERRED").first()).toBeVisible();
  await therapist.getByRole("link", { name: "Approval inbox" }).click();
  await expect(therapist.locator("div.shadow-sm", { hasText: /Release exercise to client[\s\S]*For Ananya Rao/ })).toHaveCount(0);
  const exercise = therapist.locator("div.shadow-sm", { hasText: /Release exercise to client[\s\S]*For Rohan Mehta/ }).filter({ has: therapist.getByRole("button", { name: "Approve" }) }).first();
  await expect(exercise).toBeVisible();
  await expect(exercise).toContainText("What reaches the client");
  await exercise.getByRole("button", { name: "Approve" }).click();
  await expect(therapist.getByText(/Decided \(\d+\)/)).toBeVisible();

  // 3. Beta sees it
  await beta.goto("/client");
  await expect(beta.getByRole("link", { name: "Open" })).toHaveCount(exercisesBefore + 1);
  const clientId = (await (await client.request.get("/api/auth/me")).json()).id;

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
  const plan = therapist.locator("div.shadow-sm", { hasText: /Update case plan[\s\S]*For Ananya Rao/ }).filter({ has: therapist.getByRole("button", { name: "Approve" }) }).first();
  const changes = plan.getByLabel("What changes");
  await expect(changes).toBeVisible();
  await expect(changes).toContainText("Before (current version)");
  await expect(changes).toContainText("After (new version)");
  await expect(changes).toContainText("Reduce racing thoughts at bedtime");
  await expect(changes).toContainText("Changed: update_notes");
  await expect(changes).toContainText("AI-drafted, approved by Dr Meera Krishnan on");
  await plan.getByRole("button", { name: "Approve" }).click();
  await expect(therapist.locator("div.shadow-sm", { hasText: /Update case plan/ }).filter({ has: therapist.getByRole("button", { name: "Approve" }) })).toHaveCount(0);
  await therapist.reload();
  await expect(therapist.getByText(/Decided \(\d+\)/)).toBeVisible();

  // the formulation stays the therapist's; the approved AI draft sits in separate update notes
  await therapist.goto(`/therapist/clients/${clientId}`);
  await expect(therapist.getByLabel("Update notes")).toContainText("AI-drafted, approved by Dr Meera Krishnan on");

  // briefing now flags the open homework instead of offering a second release
  await therapist.goto("/therapist");
  await therapist.getByRole("button", { name: "Prepare my day" }).click();
  await expect(therapist.getByText(/^Briefed \d+ client/)).toBeVisible();
  await expect(therapist.getByText(/Already assigned \(\d+ of \d+ completed\) - consider following up/).first()).toBeVisible();

  // 6. risky phrase in a check-in: only the fixed crisis message
  await client.goto("/client");
  await client.getByRole("link", { name: "Open" }).first().click();
  await expect(client.getByRole("button", { name: "Save check-in" })).toBeVisible();
  for (const box of await client.locator("textarea").all()) await box.fill("I want to end my life");
  for (const num of await client.locator("input[type=number]").all()) await num.fill("5");
  await client.getByRole("button", { name: "Save check-in" }).click();
  const alert = client.getByRole("alert");
  await expect(alert).toHaveText(/^You are not alone/);
  await expect(alert).toContainText(CRISIS);
  await expect(client.getByText("Check-in saved.")).toHaveCount(0);
  await expect(client.getByRole("button", { name: "Save check-in" })).toHaveCount(0);
  await expect(client.getByText("I want to end my life")).toHaveCount(0);

  // therapist is alerted (risk section, pinned)
  await therapist.goto("/therapist");
  await expect(therapist.getByRole("region", { name: "Risk alerts" })).toContainText("risk alert");
});
