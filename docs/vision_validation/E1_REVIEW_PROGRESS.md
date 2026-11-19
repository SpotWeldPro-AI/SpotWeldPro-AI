# E1 Conflict Review — Human Review Progress

**Date:** 2026-11-19  
**Task:** VISION-DATA-REAL-02  
**Gate:** E1 — Conflict Resolution  
**Status:** NOT CLEAR (0/175 resolved)

---

## Summary

| Metric | Value |
|--------|-------|
| Total conflict pairs | 175 |
| Decisions made | 0 |
| Decisions pending | 175 |
| Completion | 0.0% |
| E1 gate clear | False |
| Blocked training paths | 343 (pending conflict pairs × 2) |

No automatic adjudication decisions have been made. All 175 pairs require human review by  
a QUALITY_ENGINEER, PROCESS_ENGINEER, or SYSTEM_ADMIN.

---

## Queue by Priority

| Priority | Conflict Type | Count | Decisions |
|----------|--------------|-------|-----------|
| CRITICAL | BOTH (cross-split + label conflict) | 51 | 0 |
| HIGH | LABEL_CONFLICT | 122 | 0 |
| MEDIUM | CROSS_SPLIT_LEAKAGE | 2 | 0 |
| **TOTAL** | | **175** | **0** |

---

## Available Reviewer Decisions

| Decision | Description | Use When |
|----------|-------------|----------|
| CONFIRM_LABEL | Both labels are consistent; keep the more specific one | Labels agree or one is clearly more specific |
| CORRECT_LABEL | One label is wrong; specify correct label in notes | Reviewer can determine correct label from surface view |
| EXCLUDE_FROM_TRAINING | Exclude both paths; keep in DB | Ambiguous or irresolvable without physical test |
| INSUFFICIENT_EVIDENCE | Cannot determine correct label | Surface view genuinely insufficient |
| NEEDS_PHYSICAL_TEST | Destructive test required before label can be confirmed | kopuk, kucuk_cekirdek, cift_sac cases |

**Notes are mandatory for all decisions.** The reviewer must state the specific physical evidence or reasoning behind the decision.

---

## Defect Classes Requiring Physical Test (E1 → E4 Link)

The following defect codes in conflict pairs warrant NEEDS_PHYSICAL_TEST unless surface evidence is conclusive:

| Code | Name | Surface Classifiable | Physical Required |
|------|------|----------------------|-------------------|
| kopuk | Broken | INDICATOR only | Peel test / chisel test |
| kucuk_cekirdek | Small Nugget (indicator) | INDICATOR only | Cross-section / UT scan |
| cift_sac | Double Sheet | INDICATOR only | Cross-section |
| ok | Accepted | YES (absence of defect) | Only if nugget size disputed |

---

## Training Impact of E1 Resolution

| Scenario | Training Eligible | Eval Eligible | Surface Classifier |
|----------|-------------------|---------------|-------------------|
| Current (0 resolved) | 191 | 151 | NO-GO (need +9 train) |
| All 175 resolved (best case) | ~317 | ~193 | CONDITIONAL GO |
| All 175 excluded | 191 | 151 | NO-GO |

Resolving LABEL_CONFLICT pairs with CONFIRM_LABEL or CORRECT_LABEL is expected to unlock the most training candidates. EXCLUDE_FROM_TRAINING removes both paths from the pool.

---

## Access

ConflictReviewPage is available at the VISION → Conflict Review route.

Required roles: QUALITY_ENGINEER, PROCESS_ENGINEER, or SYSTEM_ADMIN.

Backend API: `PATCH /api/v1/annotation/conflicts/{id}`

---

## History

| Date | Decisions | Cumulative | Notes |
|------|-----------|------------|-------|
| 2026-11-14 | 0 | 0 | REAL-01 baseline — queue loaded |
| 2026-11-19 | 0 | 0 | REAL-02 — UI enhanced, no adjudications |

---

## Next Step

A QUALITY_ENGINEER must review and adjudicate conflict pairs.  
Start with the 51 CRITICAL (BOTH) pairs, which have both cross-split SHA1 collisions  
and conflicting labels — these represent the highest training data risk.
