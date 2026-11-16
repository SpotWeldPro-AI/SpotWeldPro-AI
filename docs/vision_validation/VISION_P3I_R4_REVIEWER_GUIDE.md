# Vision P3I — Conflict Review: Human Reviewer Guide

**Document:** VISION_P3I_R4_REVIEWER_GUIDE  
**Date:** 2026-11-16  
**Status:** READY FOR HUMAN REVIEW  
**Conflicts to adjudicate:** 175 (source CSV — real decisions pending)

---

## Overview

175 annotated image pairs were detected with labeling conflicts during the P3H dataset audit.
Each pair shares the same 16-character SHA-1 prefix but carries inconsistent labels, incompatible
splits, or both. All pairs must be adjudicated by a human reviewer before model training is unlocked.

**No automatic adjudication takes place. Every decision requires:**
1. Visual inspection of both images
2. Selection of one of the five decision types
3. A written note explaining your reasoning

---

## Accessing the Review Interface

1. Open a browser and navigate to: **http://localhost:5173**
2. Log in with your reviewer credentials
3. In the left sidebar, expand the **VISION** group
4. Click **CR Conflict Review**

The Conflict Review Queue page opens showing all 175 pending records.

---

## Understanding the Queue

### Priority Ordering

Work conflicts in this priority order:

| Priority | Type | Count | Reason |
|----------|------|-------|--------|
| 1 — LABEL_CONFLICT | Same image, different labels | 122 | Direct labeling error |
| 2 — BOTH | Label conflict + split leakage | 51 | Compound integrity problem |
| 3 — CROSS_SPLIT_LEAKAGE | Same image, different splits | 2 | Evaluation contamination |

Use the **Pending** filter tab to see only unresolved records.  
Use the **Physical** tab to track records marked NEEDS_PHYSICAL_TEST.  
Use the **No Evid.** tab to track records marked INSUFFICIENT_EVIDENCE.

### Reading a Conflict Card

Each card shows:
- **Conflict type badge** (LABEL_CONFLICT / BOTH / CROSS_SPLIT_LEAKAGE)
- **Status badge** (PENDING / resolved decision)
- **Label pair** — e.g., `cift_sac vs generic_bad`
- **Splits** — e.g., `train / val`
- **SHA-1 prefix** — 16-char hash linking the two records

Click a card to open the side-by-side detail panel.

### Reading the Side-by-Side Panel

| Field | Meaning |
|-------|---------|
| Label | The annotator's original label for this record |
| Split | Dataset partition (train / val / test) |
| Archive | Source ZIP file this record was extracted from |
| SHA-1 | 16-char hash — identical means the same image pixel data |
| File path | Full local path on the data drive |

---

## The Five Decision Types

### 1. CONFIRM_LABEL
**Use when:** Both labels describe the same defect category and the disagreement is a naming
inconsistency (e.g., `generic_bad` vs a legacy alias). Keep the more specific, canonical label.

**Notes must state:** Which label is correct and why (e.g., "cift_sac is the canonical term;
generic_bad is a deprecated legacy alias used before the taxonomy was finalised").

### 2. CORRECT_LABEL
**Use when:** One of the two labels is factually wrong. The image was mis-labelled.

**Notes must state:** Which path has the wrong label, what the correct label is, and your
reasoning (e.g., "path_b shows a double-sheet condition, not a generic NOK — correct to cift_sac").

### 3. EXCLUDE_FROM_TRAINING
**Use when:** Neither label can be trusted, the image is ambiguous, corrupt, or not relevant,
but you want to retain the record in the database for audit purposes.

**Notes must state:** Why both paths are excluded (e.g., "image is overexposed, defect category
indeterminate from visual inspection alone").

### 4. INSUFFICIENT_EVIDENCE
**Use when:** You cannot determine the correct label without additional context — weld parameters,
material spec, or consultation with the process engineer.

**Notes must state:** What additional evidence is needed and who should provide it.

### 5. NEEDS_PHYSICAL_TEST
**Use when:** A destructive test (cross-section, peel, or chisel test) is the only way to verify
whether the weld is a true defect or a cosmetic anomaly.

**Notes must state:** Which test is recommended and what acceptance criterion applies.

---

## Rules

| Rule | Detail |
|------|--------|
| Notes are mandatory | Blank notes are rejected by the system (HTTP 400). |
| Decisions are final | Once submitted, a decision cannot be changed. Submit carefully. |
| No self-assignment | Do not adjudicate records you originally labelled. |
| Do not use original images | Work from the archive paths shown — do not modify source files. |
| Record real observations | Do not write placeholder notes. Notes become part of the audit trail. |

---

## After All 175 Decisions

When the progress bar shows 175/175 (100%):

1. Notify the dataset administrator
2. The administrator runs `DatasetAudit.approve()` on the backend
3. The system re-evaluates `surface_classifier_go` using the corrected label set
4. If `surface_classifier_go = True`, Phase 4 model training may proceed

**Current gate status (as of 2026-11-16):**

| Gate | Status |
|------|--------|
| E1 — Conflict Resolution | OPEN — 175 real decisions pending |
| E1 gate clear | False |
| Training eligible (surface binary) | 191 / 200 minimum — 9 short |
| Eval eligible | 152 / 40 minimum — OK |
| Surface classifier GO | False |
| DatasetAudit.is_training_allowed() | False |

---

## API Reference (for programmatic access)

| Operation | Method | URL |
|-----------|--------|-----|
| List conflicts (paginated) | GET | `/api/v1/annotation/conflicts?page=1&page_size=50` |
| Filter pending only | GET | `/api/v1/annotation/conflicts?status=PENDING&page_size=50` |
| Submit a decision | PATCH | `/api/v1/annotation/conflicts/{id}` |
| Review summary | GET | `/api/v1/annotation/conflicts/review-summary` |
| Eligible counts | GET | `/api/v1/annotation/conflicts/eligible-counts` |

Decision payload (PATCH body):
```json
{
  "decision": "CONFIRM_LABEL",
  "notes": "Explanation required — minimum one meaningful sentence."
}
```

Decision values: `CONFIRM_LABEL` · `CORRECT_LABEL` · `EXCLUDE_FROM_TRAINING` · `INSUFFICIENT_EVIDENCE` · `NEEDS_PHYSICAL_TEST`

---

## Conflict Breakdown by Label Pair (top 10)

Based on the E1_CONFLICT_REVIEW_QUEUE.csv source:

| Label A | Label B | Conflict Type | Approx. Count |
|---------|---------|--------------|---------------|
| cift_sac | generic_bad | LABEL_CONFLICT | ~50 |
| yanik | generic_bad | LABEL_CONFLICT | ~30 |
| ok | generic_bad | LABEL_CONFLICT | ~20 |
| ok | ok | CROSS_SPLIT_LEAKAGE | 2 |
| (various) | (various) | BOTH | 51 |

(Exact counts visible in the Conflict Review Queue UI.)
