# SpotWeldPro AI — Deployment Readiness Checklist (P3G)

**Date:** 2026-11-14  
**Task:** VISION-P3G  
**Branch:** main  
**HEAD (pre-commit):** 5141b50  

---

## Legend

| Symbol | Meaning |
|---|---|
| ✅ | Gate cleared |
| ❌ | Gate BLOCKED |
| ⚠️ | Conditional — requires operator action |
| ⏸️ | Not executed in this environment |

---

## Section A — Migration Chain Gates

| # | Gate | Status | Evidence |
|---|---|---|---|
| A1 | `alembic.ini` present and valid | ✅ | `script_location=alembic`, DATABASE_URL override via env |
| A2 | `env.py` imports all ORM models | ✅ | `import app.models` in env.py; annotation_entities imported in models/__init__.py |
| A3 | Migration 0020 revision ID correct | ✅ | `revision = "0020_annotation_tables"` |
| A4 | Migration 0020 down_revision correct | ✅ | `down_revision = "0019_import_batches"` |
| A5 | No duplicate revision IDs | ✅ | 0019 → 0020 chain, no conflicts |
| A6 | No free slot collision | ✅ | Slot 0020 unoccupied before this file |
| A7 | Reconciliation guard present | ✅ | `if "weld_annotations" in existing: return` |
| A8 | Downgrade function present | ✅ | Drops 5 tables in reverse dependency order |

---

## Section B — Schema Correctness Gates

| # | Gate | Status | Evidence |
|---|---|---|---|
| B1 | All 5 ORM tables in migration | ✅ | weld_annotations, annotation_findings, annotation_reviews, annotation_audit_entries, conflict_adjudications |
| B2 | Column count parity (ORM vs migration) | ✅ | weld_annotations=21, findings=12, reviews=8, audit=8, conflicts=16 |
| B3 | FK CASCADE constraints correct | ✅ | 3 FK → weld_annotations.id ON DELETE CASCADE |
| B4 | Unique constraint `uq_conflict_pair` | ✅ | (sha1_16, path_a, path_b) in both ORM and migration |
| B5 | Unique constraint `uq_weld_annotations_image_path` | ✅ | image_path unique in both ORM and migration |
| B6 | 18 indexes defined in migration | ✅ | See ANNOTATION_SCHEMA_AUDIT.md §3 |
| B7 | No enum types (PostgreSQL compatibility) | ✅ | All status/decision columns use String with application-layer validation |
| B8 | JSON columns use sa.JSON (not Text) | ✅ | region_data, before_state, after_state |

---

## Section C — SQLite Validation Gates

| # | Gate | Status | Evidence |
|---|---|---|---|
| C1 | Clean DB upgrade 0019→0020 | ✅ | test_annotation_tables_migration_round_trip PASS |
| C2 | Tables present after upgrade | ✅ | All 5 annotation tables confirmed |
| C3 | Columns spot-checked | ✅ | 21 weld_annotations columns verified |
| C4 | Indexes verified | ✅ | review_status, annotator_id indexes confirmed |
| C5 | FK verified | ✅ | annotation_findings → weld_annotations FK confirmed |
| C6 | Unique constraints verified | ✅ | uq_conflict_pair confirmed |
| C7 | Downgrade 0020→0019 (clean DB) | ✅ | Annotation tables removed; import_batches intact |
| C8 | Re-upgrade after downgrade | ✅ | Tables recreated cleanly |
| C9 | Full chain upgrade (empty DB → HEAD) | ✅ | test_annotation_tables_absent_in_full_head_check PASS |
| C10 | Reconciliation guard (create_all path) | ✅ | test_annotation_tables_reconciliation_guard PASS |
| C11 | Sentinel data preserved after reconciliation | ✅ | COUNT=1 after upgrade on pre-populated DB |
| C12 | Revision stamped after reconciliation | ✅ | version_num = "0020_annotation_tables" |

---

## Section D — PostgreSQL Validation Gates

| # | Gate | Status | Notes |
|---|---|---|---|
| D1 | Docker PostgreSQL available | ⏸️ | Not running in this environment |
| D2 | POSTGRES_TEST_DATABASE_URL configured | ⏸️ | Required for `tests_postgresql/` |
| D3 | Clean PostgreSQL upgrade 0019→0020 | ⏸️ | Requires D1+D2 |
| D4 | PostgreSQL schema inspection | ⏸️ | Requires D1+D2 |
| D5 | PostgreSQL FK enforcement test | ⏸️ | Requires D1+D2 |
| D6 | Long revision ID in alembic_version | ⚠️ | `prepare_postgresql_version_table()` sets VARCHAR(255); manually verify on first deploy |
| D7 | Boolean server_default on PG | ⚠️ | `sa.text("0")` for SQLite; for PG should use `sa.text("false")` — assess on live PG |

**Operator action required (D6–D7):** Run `alembic upgrade 0020_annotation_tables` on a PostgreSQL test instance before production deployment. Confirm no errors around boolean defaults.

---

## Section E — Regression Gates

| # | Gate | Status | Evidence |
|---|---|---|---|
| E1 | Vision tests 282/282 PASS | ✅ | 265 vision + 17 migration; all PASS in 44.9s |
| E2 | P3E annotation tests 50/50 PASS | ✅ | test_vision_p3e_annotation.py |
| E3 | Migration tests 17/17 PASS | ✅ | test_migrations.py (4 new annotation tests + 13 updated) |
| E4 | Backend suite 1532 PASS | ✅ | +68 vs P3F baseline; pre-existing failures unchanged |
| E5 | No new test failures introduced | ✅ | 123 pre-existing failures, same root causes as P3F |
| E6 | Frontend TypeScript check | ⚠️ | Not re-run (no frontend changes in P3G); P3F baseline was PASS |

---

## Section F — Data Safety Gates

| # | Gate | Status | Notes |
|---|---|---|---|
| F1 | Production DB not modified | ✅ | No migration executed against production |
| F2 | Destructive operations blocked | ✅ | No DROP/TRUNCATE issued; reconciliation guard only skips DDL |
| F3 | Downgrade marked destructive | ✅ | Migration docstring warns; checklist warns |
| F4 | Downgrade NOT executed on real DB | ✅ | Downgrade only tested on fresh SQLite test DB |
| F5 | Authentication gates untouched | ✅ | No changes to auth models or JWT |
| F6 | DatasetAudit quality gate untouched | ✅ | `is_training_allowed()` logic unchanged |

---

## Section G — Deployment GO / NO-GO

### GO conditions met:
- Migration file correctly chained and idempotent ✅
- Full SQLite test coverage (upgrade, downgrade, reconciliation, data preservation) ✅
- 282 vision+migration tests PASS ✅
- 1532 backend tests PASS ✅
- No new regressions introduced ✅

### NO-GO blockers remaining:

| # | Blocker | Severity | Action |
|---|---|---|---|
| **B1** | PostgreSQL live upgrade test not executed | **HIGH** | Run `alembic upgrade 0020_annotation_tables` on a live PostgreSQL test instance before production |
| **B2** | Boolean server_default (`sa.text("0")`) not verified on PostgreSQL | **MEDIUM** | Confirm `0` or `false` works as expected on PG; update if needed |
| **B3** | Migration file untracked by git | **HIGH** | Commit `0020_annotation_tables.py` + test changes (this P3G task) |

### Verdict:

> **NO-GO for production until B1 is cleared.**  
> **CONDITIONAL GO for staging/PostgreSQL test deployment** after committing this task's changes and running the PostgreSQL test suite.

---

## Commit Scope (This Task)

Files to commit:
- `backend/alembic/versions/0020_annotation_tables.py` (new, untracked)
- `backend/tests/test_migrations.py` (updated: HEAD constant + 4 new annotation tests)
- `docs/vision_validation/VISION_P3G_MIGRATION_REPORT.md` (new)
- `docs/vision_validation/ANNOTATION_SCHEMA_AUDIT.md` (new)
- `docs/vision_validation/DEPLOYMENT_READINESS_CHECKLIST.md` (this file)

Files NOT to commit:
- `frontend/tsconfig.tsbuildinfo` (build artifact, pre-existing modification)
- `GAMIC_Deck/` (untracked, unrelated)

---

## Operator Notes

1. **On first PostgreSQL deployment:** Run `alembic current` to confirm starting revision, then `alembic upgrade head`. Check logs for the `Running upgrade 0019_import_batches -> 0020_annotation_tables` line.
2. **If annotation tables already exist on PostgreSQL:** The reconciliation guard will skip DDL and stamp the revision. Verify with `alembic current` = `0020_annotation_tables` after upgrade.
3. **Training gate:** `DatasetAudit.is_training_allowed()` remains `False` (E1–E4 gates from P3B still open). This is unchanged by P3G.
4. **Do not run downgrade** on any database that contains annotation data.
