# Real Review Operational Guide

**VISION-DATA-REAL-03 · SpotWeldPro AI**

This guide describes how to run the Conflict Review and E4 Physical Evidence acceptance
test suite against a local test environment.

---

## Prerequisites

- Python 3.12+ with backend dependencies installed (`pip install -r requirements.txt`)
- Node.js 18+ with frontend dependencies installed (`npm install` in `frontend/`)
- Playwright installed: `npx playwright install chromium`
- Port 8000 (production) may be running; test suite uses port 8001 and 5175

---

## Step 1: Create the Seeded Test Database

Run once from the `backend/` directory:

```bash
cd backend

python - <<'PY'
import os, sys
os.environ['DATABASE_URL'] = 'sqlite:///./test_real03_seed.db'
os.environ['JWT_SECRET_KEY'] = 'test-secret-real03-with-sufficient-length'

# Import to trigger table creation
from app.db.session import engine
from app.models.base import Base
Base.metadata.create_all(bind=engine)

from app.db.session import SessionLocal
from app.models.entities import User
from app.models.annotation_entities import ConflictAdjudication
from app.core.security import hash_password

with SessionLocal() as db:
    for uname, email, pw, role in [
        ("admin",   "admin@test",   "ChangeMe123!", "SYSTEM_ADMIN"),
        ("qe_test", "qe@test",      "QEpass123!",   "QUALITY_ENGINEER"),
        ("pe_test", "pe@test",      "PEpass123!",   "PROCESS_ENGINEER"),
        ("demo",    "demo@test",    "A1234",         "DEMO_USER"),
    ]:
        if not db.query(User).filter(User.username == uname).first():
            db.add(User(username=uname, email=email, full_name=uname,
                        password_hash=hash_password(pw), role=role, is_active=True))
    db.commit()

    if db.query(ConflictAdjudication).count() == 0:
        for i in range(5):
            db.add(ConflictAdjudication(
                sha1_16=f'synth{i:08d}aabb{i:04d}',
                path_a=f'/synthetic/test/image_a_{i:03d}.png',
                path_b=f'/synthetic/test/image_b_{i:03d}.png',
                label_a=['ok','capak','kopuk','kucuk_cekirdek','deformeli'][i],
                label_b=['capak','ok','generic_bad','kopuk','eksik'][i],
                split_a='train',
                split_b='val' if i % 2 == 0 else 'train',
                conflict_type=['BOTH','LABEL_CONFLICT','BOTH','LABEL_CONFLICT','CROSS_SPLIT_LEAKAGE'][i],
                source_archive_a='synthetic_archive_A.zip',
                source_archive_b='synthetic_archive_B.zip',
            ))
        db.commit()
        print('Seeded OK')
PY
```

---

## Step 2: Start the Test Backend (port 8001)

From the `backend/` directory:

```bash
DATABASE_URL=sqlite:///./test_real03_seed.db \
JWT_SECRET_KEY=test-secret-real03-with-sufficient-length \
CORS_ORIGINS="http://localhost:5174,http://localhost:5175" \
  uvicorn app.main:app --port 8001 --log-level warning &
```

Verify: `curl http://localhost:8001/api/v1/health` → `{"status":"ok",...}`

---

## Step 3: Start the Test Frontend (port 5175)

From the `frontend/` directory:

```bash
VITE_API_URL=http://localhost:8001/api/v1 npx vite --port 5175 &
```

Wait for `➜  Local: http://localhost:5175/` in the output.

---

## Step 4: Run the API Test Suite

From the `backend/` directory:

```bash
python -m pytest tests/test_vision_data_real_03.py -v
```

**Expected:** 57/57 PASS

---

## Step 5: Run the Browser Test Suite

From the `frontend/` directory:

```bash
npx playwright test e2e_real_03_review.spec.ts --config=pw_real03.config.ts --reporter=list
```

**Expected:** 16/16 PASS

---

## Test Credentials

| Username | Password | Role |
|----------|----------|------|
| admin | ChangeMe123! | SYSTEM_ADMIN |
| qe_test | QEpass123! | QUALITY_ENGINEER |
| pe_test | PEpass123! | PROCESS_ENGINEER |
| demo | A1234 | DEMO_USER |

---

## Architecture Notes

### Vite API Proxy Interceptor

The browser test spec (`e2e_real_03_review.spec.ts`) includes a `setupApiProxy(page)`
helper that intercepts all requests to `http://localhost:5175/api/v1/*` and forwards them
to `http://localhost:8001/api/v1/*`. This is necessary because:

- `ConflictReviewPage` and `E4EvidencePage` use `const API = '/api/v1/annotation'` with
  raw `fetch()`, which resolves relative to the Vite dev server origin.
- The Vite dev server (`vite.config.ts`) does not configure a backend proxy.
- The axios `client.ts` respects `VITE_API_URL`, but direct `fetch()` calls do not.

The interceptor runs transparently in the Node.js request context (no CORS restrictions)
and does not modify any source files.

### FastAPI Route Ordering

`backend/app/api/v1/annotation.py` registers E4 routes (`/e4-evidence`, `/e4-evidence/summary`)
and the image preview route **before** the parameterized `/{annotation_id}` catch-all. If
this order is reversed, FastAPI will interpret the literal path segments as `annotation_id`
parameter values and return 422.

### DB Isolation

| Environment | DB file | Port |
|-------------|---------|------|
| Production | `spotweld_gamic.db` | 8000 |
| Test | `test_real03_seed.db` | 8001 |
| pytest | `tests/test_spot_welding.db` | (in-process) |

The pytest suite (`conftest.py`) creates and tears down `tests/test_spot_welding.db`
automatically. The browser test DB (`test_real03_seed.db`) is persistent and re-used
across runs; it is not in Git.

---

## Hard Rules

These rules are enforced by the test design and must not be violated:

1. **Only SpotWeldPro AI** — no other project or service is touched.
2. **No production DB** — `spotweld_gamic.db` is never read or written by tests.
3. **No automatic decisions on real images** — all adjudication is performed on synthetic pairs.
4. **No bypass of E1–E4 gates** — gate status is asserted, never cleared by tests.
5. **No model training** — no training endpoint is called.
6. **No automatic push or deployment** — commits require manual review.
7. **Preserve unrelated work** — only test infrastructure and deliverable docs are changed.
