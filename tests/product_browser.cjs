// Real Chromium tests against the disposable Flask/SQLite product.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.SCMS_BROWSER_EXECUTABLE || undefined,
    headless: true,
    args: process.env.SCMS_BROWSER_EXECUTABLE
      ? [
          "--no-sandbox",
          "--disable-gpu",
          "--disable-software-rasterizer",
          "--no-zygote",
          "--single-process",
        ]
      : [],
  });
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const checks = [];
  async function visible(s) {
    await page.locator(s).waitFor({ state: "visible" });
  }
  async function text(s, re) {
    await page.waitForFunction(
      ({ s, re }) =>
        new RegExp(re).test(document.querySelector(s)?.textContent || ""),
      { s, re: re.source },
    );
  }
  async function login(uid) {
    await page.locator("#university_id").fill(uid);
    await page.locator("#password").fill("Test-Only-123");
    await page.locator("#auth-submit").click();
    await visible("#app-nav");
  }
  async function logout() {
    await page.locator("#logout").click();
    await visible("#auth-card");
    await page.waitForFunction(
      () =>
        !document
          .querySelector("#global-message")
          .textContent.includes("Signed in"),
    );
  }
  async function submit(severity, desc) {
    await page.locator("#tab-submit").click();
    await page.locator("#category").selectOption("Facilities");
    await page.locator("#description").fill(desc);
    await page.locator("#severity").selectOption(severity);
    await page.locator("#complaint-submit").click();
    await text("#submit-message", /Reference ID: #/);
    return Number(
      (await page.locator("#submit-message").textContent()).match(
        /Reference ID: #(\d+)/,
      )[1],
    );
  }
  async function details(id, view) {
    await page.locator(`#item-${view}-${id} [data-action=details]`).click();
    await visible(`#details-${view}-${id} h3`);
  }
  async function act(id, action, msg) {
    if (["resolve", "reject"].includes(action))
      await page.locator(`#remarks-${id}`).fill(msg);
    await page.locator(`[data-id="${id}"][data-action="${action}"]`).click();
    await text("#global-message", /updated successfully/);
    await page.locator(`#details-staff-${id}`).waitFor({ state: "hidden" });
  }
  await page.goto(process.env.SCMS_E2E_URL);
  await visible("#auth-card");
  await page.locator("#toggle-auth").click();
  await page.locator("#name").fill("Browser Student");
  await page.locator("#email").fill("browser@example.edu");
  await page.locator("#university_id").fill("STU001");
  await page.locator("#password").fill("Test-Only-123");
  await page.locator("#auth-submit").click();
  await visible("#complaint-card");
  checks.push("Student registration and automatic login");
  await page.locator("#complaint-submit").click();
  await text("#error-category", /required/);
  checks.push("Field-specific invalid submission errors");
  const first = await submit(
    "Low",
    "Browser test: fan broken <script>unsafe</script>",
  );
  await page.locator("#tab-track").click();
  await details(first, "student");
  await text(`#details-student-${first}`, /SUBMIT/);
  assert.equal(
    await page.locator(`#details-student-${first} script`).count(),
    0,
  );
  checks.push(
    "Low submission, unique reference, student tracking, safe audit display",
  );
  await logout();
  await login("FAC001");
  await text("#notifications-list", /SUBMITTED/);
  await details(first, "staff");
  await act(first, "resolve", "Fan replaced");
  checks.push("Faculty queue, notification, resolution");
  await logout();
  await login("STU001");
  await page.locator("#tab-track").click();
  await details(first, "student");
  await page.locator(`#fb-comment-${first}`).fill("Works now");
  await page.locator(`[data-id="${first}"][data-action=feedback]`).click();
  await text("#global-message", /Feedback.*recorded/);
  checks.push("Resolved-only student feedback");
  const second = await submit("Medium", "Browser test: appeal path");
  await logout();
  await login("FAC001");
  await details(second, "staff");
  await act(second, "reject", "Need more information");
  await logout();
  await login("STU001");
  await page.locator("#tab-track").click();
  await details(second, "student");
  await page.locator(`#appeal-just-${second}`).fill("Please reconsider");
  await page.locator(`[data-id="${second}"][data-action=appeal]`).click();
  await text("#global-message", /Under Appeal Review/);
  await logout();
  await login("GC001");
  await details(second, "staff");
  await act(second, "escalate");
  await logout();
  await login("DEAN01");
  await details(second, "staff");
  assert.equal(
    await page.locator(`[data-id="${second}"][data-action=escalate]`).count(),
    0,
  );
  await act(second, "resolve", "Reviewed and resolved");
  checks.push(
    "Medium routing, rejection, single appeal, Committee-to-Dean escalation, Dean ceiling",
  );
  await logout();
  await login("STU001");
  const third = await submit("High", "Browser test: final review");
  await logout();
  await login("GC001");
  await details(third, "staff");
  await act(third, "escalate");
  await logout();
  await login("DEAN01");
  await details(third, "staff");
  await act(third, "reject", "Initial final decision");
  await logout();
  await login("STU001");
  await page.locator("#tab-track").click();
  await details(third, "student");
  await page.locator(`#appeal-just-${third}`).fill("Final review requested");
  await page.locator(`[data-id="${third}"][data-action=appeal]`).click();
  await text("#global-message", /final review/);
  await logout();
  await login("DEAN01");
  await details(third, "staff");
  await text(`#details-staff-${third}`, /Final appeal review/);
  await act(third, "resolve", "Final review completed");
  checks.push("High routing and Dean-level final appeal");
  await logout();
  await login("STU001");
  const fourth = await submit("Low", "Browser test: SLA");
  execFileSync("python", [
    "-c",
    "import sqlite3,os; c=sqlite3.connect(os.environ['SCMS_E2E_DB']);c.execute(\"UPDATE complaints SET status_updated_at='2026-01-01T00:00:00Z' WHERE complaint_id=?\",(" +
      fourth +
      ",));c.commit()",
  ]);
  await logout();
  await login("DEAN01");
  await page.locator("#check-overdue").click();
  await text("#sla-summary", /1 overdue/);
  await page.locator(`[data-id="${fourth}"][data-action=sla-escalate]`).click();
  await text("#sla-message", /escalated to Grievance/);
  checks.push("Manual SLA review and authorized cross-queue escalation");
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
    true,
  );
  checks.push("Mobile viewport without horizontal overflow");
  execFileSync("python", [
    "-c",
    "import sqlite3,os; c=sqlite3.connect(os.environ['SCMS_E2E_DB']);c.execute(\"UPDATE sessions SET expires_at='2000-01-01T00:00:00Z'\");c.commit()",
  ]);
  await page.locator("#refresh-staff-queue").click();
  await visible("#auth-card");
  assert.equal(await page.locator("#staff-card").isVisible(), false);
  checks.push("Expired-session recovery clears private UI");
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ checks, pageErrors: errors }, null, 2));
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
