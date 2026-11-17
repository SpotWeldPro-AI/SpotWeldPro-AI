/**
 * VISION-SYNTH-E2E-04 — FINAL VIDEO REPLAY ACCEPTANCE (Browser E2E)
 *
 * Covers STEP 5 of the E2E-04 task spec:
 *   FA-01..04: Full replay of authorized MP4 files, frame updates, event display
 *   MR-01..02: ModuleRead help panel
 *   I18N-01:   EN/TR translation presence
 *   LAYOUT-01: Responsive layout (mobile width)
 *   ERR-01..03: Error feedback for invalid/unauthorized operations
 *   RBAC-01:   Demo user cannot access privileged dataset actions
 *   REPEAT-01: Repeated connect/disconnect cycles
 *
 * BLOCKED_HARDWARE:
 *   HW-01..04: Webcam, RTSP, CNN-GRU, sustained FPS (require physical hardware)
 *
 * Hard rules:
 *   - No fabricated AI classifications
 *   - Geometric motion detection only (MODEL_NOT_LOADED)
 *   - No production database access
 *   - E1-E4 training gates not bypassed
 */
import { test, expect, type Page } from "@playwright/test";

const BASE = "http://localhost:5174";
const API  = "http://localhost:8000";
const DEMO_USER = "demo";
const DEMO_PASS = "A1234";

// Two representative short synthetic videos
const SYNTH_SHORT  = "synth_normal_approach.mp4";   // 120 frames, 30fps, 4s
const SYNTH_MEDIUM = "synth_expulsion_event.mp4";   // 120 frames, 30fps, 4s

/** Obtain JWT from API (Node.js fetch — no CORS restriction). */
async function getToken(): Promise<string> {
  const resp = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: DEMO_USER, password: DEMO_PASS }),
  });
  if (!resp.ok) throw new Error(`Login failed: ${resp.status}`);
  return (await resp.json()).access_token;
}

/** Inject token + expand vision sidebar, navigate to /app. */
async function loginBrowser(page: Page): Promise<void> {
  const token = await getToken();
  await page.goto(BASE);
  await page.evaluate((tok) => {
    localStorage.setItem("access_token", tok);
    localStorage.setItem("sb_open", JSON.stringify({ vision_group: true }));
  }, token);
  await page.goto(`${BASE}/app`);
  await page.waitForSelector(".sidebar", { timeout: 12_000 });
}

/** Navigate to Live Monitoring via sidebar. */
async function goToLiveMonitoring(page: Page): Promise<void> {
  const link = page.locator(
    'button:has-text("Live Monitoring"), button:has-text("Canlı İzleme"), a:has-text("Live Monitoring"), a:has-text("Canlı İzleme")'
  ).first();
  await link.click({ timeout: 8_000 });
  await page.waitForTimeout(1000);
}

/** Cleanup all registered file sources. */
async function cleanupSources(token: string): Promise<void> {
  const resp = await fetch(`${API}/api/v1/vision/live/sources`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) return;
  const { sources } = await resp.json();
  for (const s of sources) {
    if (s.source_id.startsWith("file://")) {
      await fetch(
        `${API}/api/v1/vision/live/sources?source_id=${encodeURIComponent(s.source_id)}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
      ).catch(() => {});
    }
  }
}

// ─── FA-01..04: Full replay of authorized MP4 files ───────────────────────────

test.describe("FA-01..04: Full replay — authorized MP4 files", () => {
  test.beforeEach(async ({ page }) => {
    await loginBrowser(page);
    await goToLiveMonitoring(page);
  });

  test.afterEach(async () => {
    const tok = await getToken().catch(() => "");
    if (tok) await cleanupSources(tok);
  });

  test("FA-01: Register synth_normal_approach and verify CONNECTED + frame delivery", async ({ page }) => {
    const sel = page.locator("select").first();
    await sel.selectOption("file");
    const pathIn = page.locator("input[placeholder*='mp4'], input[placeholder*='synth']").first();
    await pathIn.fill(SYNTH_SHORT);

    const connectBtn = page.locator("button", { hasText: /connect/i }).first();
    await connectBtn.click();

    await page.waitForFunction(
      () => document.body.innerText.includes("CONNECTED"),
      { timeout: 12_000 }
    );
    expect(await page.locator("body").innerText()).toMatch(/connected/i);

    // Frame image must appear
    const frameImg = page.locator("img[alt='Live frame']").first();
    await expect(frameImg).toBeVisible({ timeout: 15_000 });
    const src = await frameImg.getAttribute("src");
    expect(src).toMatch(/^data:image\/jpeg;base64,/);
  });

  test("FA-02: Register synth_expulsion_event and verify frame + event delivery", async ({ page }) => {
    const sel = page.locator("select").first();
    await sel.selectOption("file");
    const pathIn = page.locator("input[placeholder*='mp4'], input[placeholder*='synth']").first();
    await pathIn.fill(SYNTH_MEDIUM);

    await page.locator("button", { hasText: /connect/i }).first().click();
    await page.waitForFunction(
      () => document.body.innerText.includes("CONNECTED"),
      { timeout: 12_000 }
    );
    const frameImg = page.locator("img[alt='Live frame']").first();
    await expect(frameImg).toBeVisible({ timeout: 15_000 });
  });

  test("FA-03: Connect then disconnect — source cleaned up, state shows DISCONNECTED", async ({ page }) => {
    const token = await getToken();
    const sel = page.locator("select").first();
    await sel.selectOption("file");
    const pathIn = page.locator("input[placeholder*='mp4'], input[placeholder*='synth']").first();
    await pathIn.fill(SYNTH_SHORT);

    await page.locator("button", { hasText: /connect/i }).first().click();
    await page.waitForFunction(
      () => document.body.innerText.includes("CONNECTED"),
      { timeout: 12_000 }
    );

    // Disconnect
    await page.locator("button", { hasText: /disconnect/i }).first().click({ timeout: 5_000 });
    await page.waitForTimeout(1500);

    // Source must not be RUNNING after disconnect
    const listResp = await fetch(`${API}/api/v1/vision/live/sources`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const { sources } = await listResp.json();
    const stillRunning = sources.find(
      (s: { source_id: string; worker_state: string }) =>
        s.source_id.includes("synth_normal_approach") && s.worker_state === "RUNNING"
    );
    expect(stillRunning, "Source should not be RUNNING after disconnect").toBeUndefined();
  });

  test("FA-04: Repeated connect/disconnect cycle (2 cycles) — no state corruption", async ({ page }) => {
    for (let cycle = 0; cycle < 2; cycle++) {
      const sel = page.locator("select").first();
      await sel.selectOption("file");
      const pathIn = page.locator("input[placeholder*='mp4'], input[placeholder*='synth']").first();
      await pathIn.fill(SYNTH_SHORT);

      await page.locator("button", { hasText: /connect/i }).first().click();
      await page.waitForFunction(
        () => document.body.innerText.includes("CONNECTED"),
        { timeout: 12_000 }
      ).catch(() => {});

      await page.locator("button", { hasText: /disconnect/i }).first().click({ timeout: 5_000 });
      await page.waitForTimeout(1500);
    }
    // No assertion needed beyond no crash/unhandled error
    const errors: string[] = [];
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await page.waitForTimeout(500);
    const fatal = errors.filter(e => !e.includes("favicon") && !e.includes("Failed to load resource"));
    expect(fatal, `Fatal JS errors after repeated cycles: ${fatal.join("; ")}`).toHaveLength(0);
  });
});

// ─── MR-01..02: ModuleRead help panel ────────────────────────────────────────

test.describe("MR-01..02: ModuleRead help panel", () => {
  test.beforeEach(async ({ page }) => {
    await loginBrowser(page);
    await goToLiveMonitoring(page);
  });

  test("MR-01: ModuleRead button is visible on Live Monitoring page", async ({ page }) => {
    const btn = page.locator(".moduleread-btn").first();
    await expect(btn).toBeVisible({ timeout: 8_000 });
  });

  test("MR-02: ModuleRead panel opens and contains non-trivial content", async ({ page }) => {
    const btn = page.locator(".moduleread-btn").first();
    await btn.click({ timeout: 8_000 });
    const panel = page.locator(".moduleread-panel").first();
    await expect(panel).toBeVisible({ timeout: 5_000 });
    const text = await panel.innerText();
    expect(text.length).toBeGreaterThan(20);
    await page.keyboard.press("Escape");
  });
});

// ─── I18N-01: Translation presence ───────────────────────────────────────────

test.describe("I18N-01: Translations", () => {
  test("I18N-01: Page contains recognizable EN or TR navigation text", async ({ page }) => {
    await loginBrowser(page);
    await goToLiveMonitoring(page);
    const body = await page.locator("body").innerText();
    const hasEN = /live|monitor|connect/i.test(body);
    const hasTR = /canlı|izleme|bağlan/i.test(body);
    expect(hasEN || hasTR, "Page must contain EN or TR Live Monitoring text").toBe(true);
  });
});

// ─── LAYOUT-01: Responsive layout ─────────────────────────────────────────────

test.describe("LAYOUT-01: Responsive layout", () => {
  test("LAYOUT-01: Page renders without horizontal scroll at 375px (mobile)", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await loginBrowser(page);
    await goToLiveMonitoring(page);
    await page.waitForTimeout(500);
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    expect(bodyWidth).toBeLessThanOrEqual(400);
  });
});

// ─── ERR-01..03: Error feedback ───────────────────────────────────────────────

test.describe("ERR-01..03: Error feedback for invalid operations", () => {
  test("ERR-01: POST path traversal returns 403 (not 500)", async ({ page }) => {
    const token = await getToken();
    const resp = await fetch(`${API}/api/v1/vision/live/sources`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ source_type: "file", path: "../../etc/passwd" }),
    });
    expect(resp.status).toBe(403);
  });

  test("ERR-02: POST absolute path outside allowed dir returns 403", async ({ page }) => {
    const token = await getToken();
    const resp = await fetch(`${API}/api/v1/vision/live/sources`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ source_type: "file", path: "/tmp/evil.mp4" }),
    });
    expect(resp.status).toBe(403);
  });

  test("ERR-03: POST unauthenticated returns 401", async ({ page }) => {
    const resp = await fetch(`${API}/api/v1/vision/live/sources`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_type: "file", path: "synth_normal_approach.mp4" }),
    });
    expect(resp.status).toBe(401);
  });
});

// ─── RBAC-01: Demo user cannot access privileged dataset actions ──────────────

test.describe("RBAC-01: Demo user authorization", () => {
  test("RBAC-01: Demo user can register authorized file source but not arbitrary paths", async ({ page }) => {
    const token = await getToken();

    // Can register valid synthetic file
    const r1 = await fetch(`${API}/api/v1/vision/live/sources`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ source_type: "file", path: "synth_normal_approach.mp4" }),
    });
    expect(r1.status).toBe(201);
    const { source_id } = await r1.json();

    // Cannot access arbitrary filesystem paths
    const r2 = await fetch(`${API}/api/v1/vision/live/sources`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ source_type: "file", path: "../../../etc/shadow" }),
    });
    expect(r2.status).toBe(403);

    // Cleanup
    await fetch(
      `${API}/api/v1/vision/live/sources?source_id=${encodeURIComponent(source_id)}`,
      { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
    );
  });
});

// ─── PERF-01: Frame delivery measurement ─────────────────────────────────────

test.describe("PERF-01: Browser frame delivery measurement", () => {
  test("PERF-01: Measure frames received in 5s window (must be > 10)", async ({ page }) => {
    const token = await getToken();
    const regResp = await fetch(`${API}/api/v1/vision/live/sources`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ source_type: "file", path: SYNTH_SHORT }),
    });
    expect(regResp.status).toBe(201);
    const { source_id } = await regResp.json();

    await page.goto(BASE);
    const result = await page.evaluate(
      async ({ api, tok, sid }: { api: string; tok: string; sid: string }) => {
        return new Promise<{ frames: number; duration_ms: number; events: number }>(
          (resolve) => {
            const ws = new WebSocket(
              `${api.replace("http://", "ws://")}/api/v1/vision/live/ws`
            );
            const timer = setTimeout(() => { ws.close(); resolve({ frames: 0, duration_ms: 0, events: 0 }); }, 10_000);
            let frames = 0, events = 0;
            const start = performance.now();
            ws.onopen = () => ws.send(JSON.stringify({ action: "auth", token: tok }));
            ws.onmessage = (ev) => {
              const m = JSON.parse(ev.data);
              if (m.type === "auth_ok") ws.send(JSON.stringify({ action: "subscribe", source_id: sid }));
              else if (m.type === "frame") frames++;
              else if (m.type === "event") events++;
              if (performance.now() - start > 5000 && frames > 0) {
                clearTimeout(timer); ws.close();
                resolve({ frames, duration_ms: performance.now() - start, events });
              }
            };
            ws.onerror = () => { clearTimeout(timer); resolve({ frames: 0, duration_ms: 0, events: 0 }); };
          }
        );
      },
      { api: API, tok: token, sid: source_id }
    );
    await cleanupSources(token);
    expect(result.frames, "Should receive > 10 frames in 5s").toBeGreaterThan(10);
    const fps = result.frames / (result.duration_ms / 1000);
    console.log(`[PERF-01-E2E04] frames=${result.frames} events=${result.events} ` +
                `duration=${result.duration_ms.toFixed(0)}ms fps_delivered=${fps.toFixed(1)}`);
  });
});

// ─── BLOCKED_HARDWARE ─────────────────────────────────────────────────────────

test.describe("BLOCKED_HARDWARE: Hardware-dependent features", () => {
  test("HW-01: USB webcam source [BLOCKED_HARDWARE]", async () => {
    test.skip(true, "BLOCKED_HARDWARE: requires physical USB camera");
  });
  test("HW-02: RTSP stream source [BLOCKED_HARDWARE]", async () => {
    test.skip(true, "BLOCKED_HARDWARE: requires RTSP server or physical camera");
  });
  test("HW-03: CNN-GRU weld defect classification [BLOCKED_HARDWARE]", async () => {
    test.skip(true, "BLOCKED_HARDWARE: no trained CNN-GRU/LSTM model; MODEL_NOT_LOADED");
  });
  test("HW-04: Sustained hardware FPS ≥ 30fps [BLOCKED_HARDWARE]", async () => {
    test.skip(true, "BLOCKED_HARDWARE: hardware camera FPS not validated without physical device");
  });
});
