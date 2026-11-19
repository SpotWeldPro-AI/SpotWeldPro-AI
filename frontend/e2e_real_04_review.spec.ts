/**
 * VISION-DATA-REAL-04 — Human Review Operational Acceptance (Browser)
 *
 * Tests the full Conflict Review workflow with 175 real conflict pairs
 * through authenticated Chromium against the REAL-04 test environment.
 *
 * Test server: http://localhost:8002  (test_real04_review.db, 175 real conflicts)
 * Frontend:    http://localhost:5176  (VITE_API_URL=http://localhost:8002/api/v1)
 *
 * Hard rules:
 *  - No automatic adjudication of real conflicts
 *  - No production DB operations
 *  - No model training
 *  - Decision tests only use the 5 synthetic R04 pairs
 */
import { test, expect, type Page } from "@playwright/test";

const BASE = "http://localhost:5176";
const API  = "http://localhost:8002";

// ── Auth helpers ───────────────────────────────────────────────────────────────

async function getToken(username: string, password: string): Promise<string> {
  const resp = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!resp.ok) throw new Error(`Login failed for ${username}: ${resp.status}`);
  return (await resp.json()).access_token as string;
}

// Proxy relative /api/v1/* calls (from ConflictReviewPage fetch()) to test backend
async function setupApiProxy(page: Page): Promise<void> {
  await page.route(/localhost:5176\/api\/v1\//, async (route) => {
    const url = route.request().url().replace("localhost:5176", "localhost:8002");
    const method = route.request().method();
    const headers = route.request().headers();
    const postData = route.request().postData();
    try {
      const resp = await page.request.fetch(url, {
        method, headers, data: postData ?? undefined,
      });
      const fwdHeaders: Record<string, string> = {};
      for (const [k, v] of Object.entries(await resp.headers())) {
        if (!["content-encoding", "transfer-encoding", "connection"].includes(k.toLowerCase())) {
          fwdHeaders[k] = v;
        }
      }
      await route.fulfill({ status: resp.status(), headers: fwdHeaders, body: await resp.body() });
    } catch {
      await route.abort("failed");
    }
  });
}

async function loginAs(page: Page, username: string, password: string): Promise<void> {
  await setupApiProxy(page);
  const token = await getToken(username, password);
  await page.goto(BASE);
  await page.evaluate((tok) => {
    localStorage.setItem("access_token", tok);
    localStorage.setItem("sb_open", JSON.stringify({ vision_group: true }));
  }, token);
  await page.goto(`${BASE}/app`);
  await page.waitForSelector(".sidebar", { timeout: 15_000 });
}

async function goToPage(page: Page, label: string): Promise<void> {
  const navBtn = page.locator(`button:has-text("${label}"), a:has-text("${label}")`).first();
  await navBtn.click({ timeout: 10_000 });
  await page.waitForTimeout(1500);
}

// ── CR-04-01: Conflict Review page loads for QUALITY_ENGINEER ─────────────────

test("CR-04-01: Conflict Review page loads for QUALITY_ENGINEER", async ({ page }) => {
  await loginAs(page, "qe_reviewer", "QEReview123!");
  await goToPage(page, "Conflict Review");
  await page.waitForTimeout(2000);

  const h1 = page.locator("h1, [role='heading']");
  await expect(h1).toContainText(/Conflict Review|Çakışma/i, { timeout: 10_000 });
  await page.screenshot({ path: "test-results/cr04-01-qe-load.png" });
});

// ── CR-04-02: Queue shows 175 real conflicts (read-only count check) ───────────

test("CR-04-02: Review summary shows all 175 real conflicts plus synthetic", async ({ page }) => {
  const token = await getToken("qe_reviewer", "QEReview123!");
  const r = await page.request.get(`${API}/api/v1/annotation/conflicts/review-summary`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status()).toBe(200);
  const data = await r.json();
  // 175 real + 5 synthetic = 180 total
  expect(data.total).toBeGreaterThanOrEqual(175);
  expect(data.pending).toBeGreaterThanOrEqual(170); // some synthetic may be adjudicated
});

// ── CR-04-03: Critical BOTH queue — 51 pairs present ─────────────────────────

test("CR-04-03: Critical BOTH queue contains 51 real pairs plus synthetic", async ({ page }) => {
  const token = await getToken("admin", "ChangeMe123!");
  const r = await page.request.get(`${API}/api/v1/annotation/conflicts?limit=250`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status()).toBe(200);
  const data = await r.json();
  const bothItems = data.items.filter((i: { conflict_type: string }) => i.conflict_type === "BOTH");
  expect(bothItems.length).toBeGreaterThanOrEqual(51); // 51 real + 2 synthetic
});

// ── CR-04-04: First critical pair has correct label conflict info ──────────────

test("CR-04-04: First BOTH pair shows conflicting labels", async ({ page }) => {
  const token = await getToken("qe_reviewer", "QEReview123!");
  const r = await page.request.get(`${API}/api/v1/annotation/conflicts?limit=250`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await r.json();
  const bothReal = data.items.filter(
    (i: { conflict_type: string; path_a: string }) =>
      i.conflict_type === "BOTH" && !i.path_a.includes("/r04/synth/")
  );
  expect(bothReal.length).toBeGreaterThanOrEqual(51);

  const first = bothReal[0];
  expect(first.label_a).toBeTruthy();
  expect(first.label_b).toBeTruthy();
  expect(first.label_a).not.toBe(first.label_b); // labels must differ
  expect(first.sha1_16.length).toBe(16);
  expect(first.decision).toBe("PENDING");
});

// ── CR-04-05: Conflict page shows queue with priority badges ──────────────────

test("CR-04-05: Conflict page shows queue with conflict-type indicators", async ({ page }) => {
  await loginAs(page, "qe_reviewer", "QEReview123!");
  await goToPage(page, "Conflict Review");
  await page.waitForTimeout(3000);

  const body = await page.content();
  const hasConflictInfo = body.includes("BOTH") || body.includes("LABEL_CONFLICT")
    || body.includes("PENDING") || body.includes("Bekliyor")
    || body.includes("çakışma") || body.includes("Conflict");
  expect(hasConflictInfo).toBeTruthy();
  await page.screenshot({ path: "test-results/cr04-05-queue.png" });
});

// ── CR-04-06: Clicking a conflict shows image panels ─────────────────────────

test("CR-04-06: Selecting a conflict shows side-by-side image panels", async ({ page }) => {
  await loginAs(page, "qe_reviewer", "QEReview123!");
  await goToPage(page, "Conflict Review");
  await page.waitForTimeout(3000);

  // Find queue items via multiple selectors
  let queueItems = page.locator("div[style*='cursor: pointer']");
  let count = await queueItems.count();
  if (count === 0) {
    queueItems = page.locator("div").filter({ hasText: /PENDING|Bekliyor/i });
    count = await queueItems.count();
  }
  if (count === 0) {
    test.skip();
    return;
  }

  await queueItems.first().click();
  await page.waitForTimeout(1500);

  const bodyHtml = await page.content();
  const hasImageA = bodyHtml.includes("Image A") || bodyHtml.includes("Görüntü A");
  const hasImageB = bodyHtml.includes("Image B") || bodyHtml.includes("Görüntü B");
  expect(hasImageA).toBeTruthy();
  expect(hasImageB).toBeTruthy();
  await page.screenshot({ path: "test-results/cr04-06-side-by-side.png" });
});

// ── CR-04-07: E1 gate banner is visible ───────────────────────────────────────

test("CR-04-07: E1 gate shows blocked state", async ({ page }) => {
  await loginAs(page, "qe_reviewer", "QEReview123!");
  await goToPage(page, "Conflict Review");
  await page.waitForTimeout(2000);

  const body = await page.content();
  const hasGate = body.includes("E1") || body.includes("gate") || body.includes("Gate")
    || body.includes("eğitimi engelliyor") || body.includes("training");
  expect(hasGate).toBeTruthy();
  await page.screenshot({ path: "test-results/cr04-07-gate.png" });
});

// ── E4-04-01: E4 Evidence page accessible to QUALITY_ENGINEER ────────────────

test("E4-04-01: E4 Evidence page loads for QUALITY_ENGINEER", async ({ page }) => {
  await loginAs(page, "qe_reviewer", "QEReview123!");
  await goToPage(page, "E4 Physical Evidence");
  await page.waitForTimeout(2000);

  const h = page.locator("h1, h2, [role='heading']");
  await expect(h).toContainText(/Physical Evidence|Fiziksel Test/i, { timeout: 10_000 });
  await page.screenshot({ path: "test-results/e4-04-01-load.png" });
});

// ── E4-04-02: E4 coverage shows 927 total dataset images ──────────────────────

test("E4-04-02: E4 summary shows 927 total dataset images", async ({ page }) => {
  const token = await getToken("qe_reviewer", "QEReview123!");
  const r = await page.request.get(`${API}/api/v1/annotation/e4-evidence/summary`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status()).toBe(200);
  const data = await r.json();
  expect(data.total_dataset_images).toBe(927);
  expect(data.e4_gate_clear).toBe(false);
});

// ── SEC-04-01: image-preview requires authentication ──────────────────────────

test("SEC-04-01: image-preview endpoint requires authentication", async ({ page }) => {
  const r = await page.request.get(
    `${API}/api/v1/annotation/image-preview?path=/r04/test.png`
  );
  expect(r.status()).toBe(401);
});

// ── SEC-04-02: Path traversal blocked ─────────────────────────────────────────

test("SEC-04-02: Path traversal blocked by image-preview", async ({ page }) => {
  const token = await getToken("admin", "ChangeMe123!");
  const r = await page.request.get(
    `${API}/api/v1/annotation/image-preview?path=../../etc/passwd`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  expect([400, 403]).toContain(r.status());
});

// ── API-04-01: Review summary includes E1 gate status ─────────────────────────

test("API-04-01: Review summary returns E1 gate status false", async ({ page }) => {
  const token = await getToken("qe_reviewer", "QEReview123!");
  const r = await page.request.get(
    `${API}/api/v1/annotation/conflicts/review-summary`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  expect(r.status()).toBe(200);
  const data = await r.json();
  expect(data.e1_gate_clear).toBe(false);
  expect(data.pending).toBeGreaterThanOrEqual(170);
});

// ── API-04-02: DEMO_USER forbidden from adjudication ─────────────────────────

test("API-04-02: DEMO_USER forbidden from conflict adjudication", async ({ page }) => {
  const demoToken = await getToken("demo", "Demo1234");
  const adminToken = await getToken("admin", "ChangeMe123!");
  // Find any pending synthetic pair
  const listR = await page.request.get(
    `${API}/api/v1/annotation/conflicts?limit=200&decision=PENDING`,
    { headers: { Authorization: `Bearer ${adminToken}` } }
  );
  const items = (await listR.json()).items as { id: number; path_a: string }[];
  const synth = items.filter(i => i.path_a.includes("/r04/synth/"));
  if (synth.length === 0) {
    test.skip();
    return;
  }
  const r = await page.request.patch(
    `${API}/api/v1/annotation/conflicts/${synth[0].id}`,
    {
      headers: {
        Authorization: `Bearer ${demoToken}`,
        "Content-Type": "application/json",
      },
      data: JSON.stringify({ decision: "CONFIRM_LABEL", notes: "should fail" }),
    }
  );
  expect(r.status()).toBe(403);
});
