# P3G PostgreSQL Verification Report

**Date:** 2026-11-14  
**Branch:** main  
**HEAD at P3G commit:** 7ba19eb  
**Verification status:** PASS

---

## Scope

This report documents the PostgreSQL verification pass for migration `0020_annotation_tables`, which
was introduced in P3G.  The goal was to confirm that the migration applies cleanly on a real
PostgreSQL instance, that the resulting schema matches the ORM models in `annotation_entities.py`,
and that the reconciliation guard preserves existing data when the tables were previously created
via `Base.metadata.create_all()`.

---

## Test Environment

| Item | Value |
|------|-------|
| Container image | `postgres:16-alpine` |
| PostgreSQL version | 16.15 on x86_64-pc-linux-musl |
| Docker port | 15432 (isolated; not production) |
| Python driver | psycopg 3.3.6 |
| Test databases | `swtest_p3g` (fresh upgrade), `swtest_p3g_reconcile` (reconciliation) |

The container was created exclusively for this verification pass and is not connected to any
production Neon or Render database.

---

## Bug Found and Fixed: Boolean server_default

### Root Cause

The initial migration used `server_default=sa.text("0")` and `server_default=sa.text("1")` for
`Boolean` columns.  PostgreSQL rejects an integer literal as a default for a `BOOLEAN` column:

```
psycopg.errors.DatatypeMismatch: column "is_roi_cropped" is of type boolean
but default expression is of type integer
```

SQLite accepts `0`/`1` for boolean columns silently, so the bug was invisible in the SQLite test
suite.

### Fix

| Column | Table | Before | After |
|--------|-------|--------|-------|
| `is_roi_cropped` | `weld_annotations` | `sa.text("0")` | `sa.false()` |
| `annotation_markup_removed` | `weld_annotations` | `sa.text("0")` | `sa.false()` |
| `export_eligible` | `weld_annotations` | `sa.text("0")` | `sa.false()` |
| `requires_physical_confirmation` | `annotation_findings` | `sa.text("0")` | `sa.false()` |
| `is_surface_classifiable` | `annotation_findings` | `sa.text("1")` | `sa.true()` |

Float columns (`max_markup_ratio`, `confidence`) correctly retained `sa.text("0")` — PostgreSQL
accepts an integer literal for `double precision`.

---

## Migration Upgrade — PASS

Full chain `0001 → 0020_annotation_tables` applied in a single `alembic upgrade head` call
(exit code 0).  All 20 steps logged without error.

`alembic_version` confirmed as `0020_annotation_tables` after upgrade.

---

## Schema Verification — PASS

Columns verified via `information_schema.columns`:

| Column | Table | Type | Default |
|--------|-------|------|---------|
| `is_roi_cropped` | `weld_annotations` | boolean | `false` |
| `annotation_markup_removed` | `weld_annotations` | boolean | `false` |
| `export_eligible` | `weld_annotations` | boolean | `false` |
| `max_markup_ratio` | `weld_annotations` | double precision | `0` |
| `is_surface_classifiable` | `annotation_findings` | boolean | `true` |
| `requires_physical_confirmation` | `annotation_findings` | boolean | `false` |
| `confidence` | `annotation_findings` | double precision | `0` |

Additional checks:
- All 5 annotation tables present
- `uq_conflict_pair` unique constraint on `conflict_adjudications` ✓
- `annotation_findings.annotation_id` FK → `weld_annotations.id` ON DELETE CASCADE ✓
- 7 indexes on `weld_annotations` (including unique index for `image_path`) ✓

---

## Reconciliation Guard — PASS

Test database `swtest_p3g_reconcile`:

1. Upgraded to `0019_import_batches` via Alembic
2. Called `Base.metadata.create_all()` directly (simulating the P3E development path)
3. Inserted sentinel row `/pg_sentinel.png` into `weld_annotations`
4. Ran `alembic upgrade 0020_annotation_tables`
5. Result: `alembic_version = "0020_annotation_tables"`, sentinel row count = **1**

**Data preserved; revision stamped.  Reconciliation guard works correctly on PostgreSQL.**

---

## Test Suite Results

### SQLite migration tests — 17/17 PASS

All 17 tests in `backend/tests/test_migrations.py` pass after the Boolean fix, including the 4
annotation-specific tests added in P3G:

- `test_annotation_tables_migration_round_trip` ✓
- `test_annotation_tables_reconciliation_guard` ✓
- `test_annotation_migration_down_revision_is_correct` ✓
- `test_annotation_tables_absent_in_full_head_check` ✓

### PostgreSQL foundation tests — 5/5 PASS

`backend/tests_postgresql/test_postgresql_foundation.py` with
`POSTGRES_TEST_DATABASE_URL=postgresql+psycopg://...@localhost:15432/swtest_p3g`:

- `test_fresh_postgresql_dialect_and_alembic_head` ✓ (`EXPECTED_HEAD` updated from
  `0012_electrode_weldgun_weldschedule_persistence` → `0020_annotation_tables`)
- `test_postgresql_upgrade_from_earlier_revision_preserves_full_revision_id` ✓
- `test_postgresql_transaction_commit_and_rollback` ✓
- `test_postgresql_enforces_foreign_key_constraint` ✓
- `test_governed_idempotency_persists_and_enforces_uniqueness` ✓

### Pre-existing PostgreSQL test failures (not P3G)

The following failures exist in `tests_postgresql/` and are **unrelated to annotation tables**.
They pre-date P3G and are not regressions:

| File | Failure cause |
|------|---------------|
| `test_governed_evidence_verification_negative_paths_e2e.py` | `ImportError: cannot import name 'RuleSourceType'` (collection error) |
| `test_governed_lifecycle_negative_paths_e2e.py` | Same `RuleSourceType` import error |
| `test_governed_happy_path_e2e.py` | Pre-existing governance revision logic failure |
| `test_governed_historical_staleness_e2e.py` | Pre-existing |
| `test_governed_active_revision_supersession_e2e.py` | Pre-existing |
| `test_governed_current_revision_resolution_e2e.py` | Pre-existing |
| `test_postgresql_engineering_library.py` | Pre-existing engineering library constraint |

None of these failures involve `weld_annotations`, `annotation_findings`, `annotation_reviews`,
`annotation_audit_entries`, or `conflict_adjudications`.

---

## Changes in This Verification Pass

| File | Change |
|------|--------|
| `backend/alembic/versions/0020_annotation_tables.py` | 5 Boolean `server_default` fixed (`sa.false()`/`sa.true()`) |
| `backend/tests_postgresql/test_postgresql_foundation.py` | `EXPECTED_HEAD` updated to `0020_annotation_tables` |
| `docs/vision_validation/VISION_P3G_POSTGRESQL_VERIFICATION.md` | This report (new) |

---

## Conclusion

Migration `0020_annotation_tables` applies cleanly on PostgreSQL 16 after correcting the Boolean
`server_default` values.  The reconciliation guard preserves pre-existing annotation data.  All
SQLite migration tests and all PostgreSQL foundation tests pass.  The migration is ready for
production deployment.
