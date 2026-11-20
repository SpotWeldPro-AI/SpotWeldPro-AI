# STATIC-VISION-LIVE-02 Report

**Task:** Fix HTTP 404 in Live Static Inspection  
**Date:** 2026-11-20  
**GIT_HEAD:** `223ccc6`  
**Status:** FIXED

---

## ROOT_CAUSE

Axios `combineURLs()` strips the leading `/` from the request path and string-concatenates it onto `baseURL`. Because `apiClient`'s `baseURL` already includes `/api/v1` (e.g. `https://spotweldpro-ai-api.onrender.com/api/v1`), any request path that also starts with `/api/v1` produces a doubled prefix.

```
baseURL:   https://host/api/v1
path:      /api/v1/vision/static/inspect   ← had /api/v1
result:    https://host/api/v1/api/v1/vision/static/inspect  ← 404
```

All other API calls in `client.ts` use paths **without** the `/api/v1` prefix (e.g. `/auth/me`, `/weld-analysis`). `StaticInspectionPage.tsx` was the only file that included the prefix in an `apiClient` call, making it the sole broken endpoint.

---

## FAILING_ENDPOINT

```
POST /api/v1/api/v1/vision/static/inspect   ← actual URL hit in production
POST /api/v1/vision/static/inspect           ← correct URL
```

## HTTP_METHOD

`POST` (multipart/form-data upload)

---

## Explanation of Previous "Timeout" vs Current "404"

The two observed errors are consistent with the same root-cause URL:

| Scenario | Behaviour |
|----------|-----------|
| Render Free backend **cold-starting** | TCP connect queued ~30 s; Axios 15 s timeout fires first → `"timeout of 15000ms exceeded"` |
| Render Free backend **warm** | Wrong URL `…/api/v1/api/v1/…` returns FastAPI 404 immediately → `"Request failed with status code 404"` |

The wrong URL existed throughout; the error message changed as backend availability changed.

---

## FIX

**File:** `frontend/src/pages/StaticInspectionPage.tsx`  
**Line:** 168

```diff
- '/api/v1/vision/static/inspect', fd,
+ '/vision/static/inspect', fd,
```

One character change. The resulting URL is now:
```
https://spotweldpro-ai-api.onrender.com/api/v1/vision/static/inspect  ✓
```

---

## FRONTEND_COMMIT

`223ccc6` — `fix(frontend): fix HTTP 404 in Static Inspection — remove /api/v1 double prefix`

## BACKEND_COMMIT

No backend change required. The backend endpoint `POST /api/v1/vision/static/inspect` is correct and already deployed (`48cfb65` in `spotweldpro/main`).

---

## TEST_RESULTS

### Backend unit tests

| Test suite | Tests | Pass | Skip | Fail |
|-----------|------:|-----:|-----:|-----:|
| `test_vision_api.py` | 14 | 14 | 0 | 0 |
| `test_vision_static_analysis.py` | 18 | 18 | 0 | 0 |
| `test_vision_preprocessing.py` | 21 | 21 | 0 | 0 |
| **Total** | **53** | **53** | **0** | **0** |

### Frontend TypeScript + production build

```
TERM_001_GATE=PASS
TSC: clean (no errors)
Vite production build: ✓ built in 7.39s
```

### Endpoint verification

The endpoint `POST /api/v1/vision/static/inspect` returns HTTP 200 with a valid `StaticInspectionResult` when called via `TestClient` with an authenticated user and a synthetic PNG fixture (all 14 `test_vision_api.py` tests confirm this).

---

## Other Affected Files (Pre-existing, Not Fixed in This Task)

Two other pages have similar URL construction issues that are pre-existing and not caused by this change. They are documented here for awareness:

### `EnergyPage.tsx:1140`

```js
const url = '/api/v1/energy/import/template'
a.href = url  // relative URL → goes to frontend domain, not backend
```

This `<a>` download resolves to `https://spotweldpro-ai-demo.onrender.com/api/v1/energy/import/template` (the **frontend** domain) which serves the React SPA, not the CSV. Additionally, the endpoint requires authentication which a bare `<a>` link cannot supply. **Recommended fix:** Use `client.get('/energy/import/template', { responseType: 'blob' })` and create an object URL.

### `LiveMonitoringPage.tsx:57,173,203`

```js
const VITE_API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
// ...
fetch(`${VITE_API}/api/v1/vision/live/sources`, ...)
```

Since `VITE_API_URL` = `https://host/api/v1`, the fetch URL becomes `https://host/api/v1/api/v1/vision/live/sources` — same double prefix. The Live Monitoring module requires a physical camera connected to the backend host, so this is not a demo-critical path.

---

## REQUIRED_DEPLOYMENT_ACTION

1. **Push `223ccc6` to `spotweldpro` remote** (requires manual authorization):
   ```bash
   git push spotweldpro main
   ```
2. **Render: redeploy `spotweldpro-ai-demo` frontend** — Render will rebuild and redeploy automatically on push, or trigger manually from the Render dashboard.
3. **No backend redeployment required** — the backend endpoint is already correctly deployed.
4. **No environment variable changes required** — `VITE_API_URL` should remain as `https://spotweldpro-ai-api.onrender.com/api/v1`.

### Deployment checklist

| Item | Status |
|------|--------|
| `VITE_API_URL` set in Render frontend env | Confirm set to `https://spotweldpro-ai-api.onrender.com/api/v1` |
| `CORS_ORIGINS` set in Render backend env | Confirm includes `https://spotweldpro-ai-demo.onrender.com` |
| `HOSTED_DEMO=true` in backend env | Required — enforces CORS validation at startup |
| `opencv-python-headless>=4.8` in `requirements.txt` | ✓ Already present |
| `python-multipart>=0.0.7` in `requirements.txt` | ✓ Already present |
| Backend Dockerfile uses `python:3.12-slim` | ✓ OpenCV headless works without system libs on this base |

---

## Hard Rules Observed

1. **No production database modification** — only frontend source code changed.
2. **No model training** — no training endpoint was called.
3. **No bypass of E1-E4 gates** — all gates unaffected.
4. **No fabricated analysis results** — `NOT_EVALUATED` returned when no acceptance criteria supplied.
5. **No automatic push or deployment** — commit `223ccc6` requires manual push authorization.
6. **No changes outside SpotWeldPro AI** — all changes confined to this repository.
