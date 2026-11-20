# SpotWeldPro AI — Live Demo Deployment Checklist

**Version:** VISION-AI-REVIEW-02  
**Date:** 2026-11-20  
**HEAD to deploy:** `6929644`  
**Remote:** `spotweldpro` → `https://github.com/SpotWeldPro-AI/SpotWeldPro-AI.git`

---

## Pre-Push Verification

- [ ] `git status --short` shows only untracked files (no staged or modified tracked files)
- [ ] `git log spotweldpro/main..HEAD --oneline` shows exactly 3 commits
- [ ] No `.env`, `.db`, credential files in `git diff spotweldpro/main..HEAD --name-only`
- [ ] `npm test -- --run` → 718/718 PASS
- [ ] `npx tsc --noEmit` → 0 errors
- [ ] `npm run build` → clean build, no errors

---

## Deployment Steps

```bash
# From C:\Users\ilhan\SpotWeldPro-AI
git push spotweldpro main
```

Render will auto-detect the push and redeploy both services.  
Deploy time: ~3–5 minutes for backend (Docker build), ~1–2 minutes for frontend (static).

---

## Post-Deploy Backend Verification

```bash
# 1. Health check (wait for cold start if needed, up to 90s)
curl https://spotweldpro-ai-api.onrender.com/api/v1/health
# Expected: {"status":"ok","service":"spot-welding-platform"}

# 2. DEMO_USER login
curl -s -X POST https://spotweldpro-ai-api.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"A1234"}'
# Expected: {"access_token": "...", "token_type": "bearer"}

# 3. Vision review endpoint present (replace TOKEN)
curl -s "https://spotweldpro-ai-api.onrender.com/api/v1/vision/static/inspect/test-deploy-check/reviews" \
  -H "Authorization: Bearer TOKEN"
# Expected: [] — NOT 404

# 4. Static inspection with synthetic PNG
curl -s -X POST https://spotweldpro-ai-api.onrender.com/api/v1/vision/static/inspect \
  -H "Authorization: Bearer TOKEN" \
  -F "image=@/path/to/synth_spatter.png" \
  -F "image_type=SURFACE" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('status:', d['status']); [print('  DETECTED:', f['code']) for f in d.get('visual_findings',[]) if f['status']=='DETECTED']"
# Expected: status: NOT_EVALUATED; DETECTED: SURFACE_SPATTER
```

---

## Post-Deploy Frontend Verification

1. Open `https://spotweldpro-ai-demo.onrender.com/login`
2. Click "Demo Girişi" / auto-filled demo credentials → login
3. Navigate to "Statik İnceleme" in sidebar
4. Upload `synth_spatter.png` → click "Muayeneyi Çalıştır"
5. Verify:
   - [ ] NOK verdict badge visible
   - [ ] "Yüzey Sıçraması" in findings card
   - [ ] "Mühendis Yorumu Ekle" button visible
6. Click "Mühendis Yorumu Ekle"
7. Verify:
   - [ ] Panel opens with "Mühendis Değerlendirmesi" title
   - [ ] "Yorum eğitim etiketi değildir." subtitle present
   - [ ] All 3 verdict buttons (Onaylıyorum / Katılmıyorum / İleri İnceleme)
   - [ ] Comment min-10 validation works
8. Submit a comment (min 10 chars) → verify "Yorum kaydedildi."
9. Reopen panel → verify comment appears in "Önceki Yorumlar"
10. Toggle page lang to EN → verify "Engineer Comment" / "Engineer Review"

---

## Rollback Procedure

Only use if a critical regression is confirmed post-deploy.

```bash
# View what will be rolled back to
git log spotweldpro/main~3..spotweldpro/main --oneline

# Roll back to the commit before the 3 new ones
git push spotweldpro spotweldpro/main~3:main --force
```

**WARNING:** Force push overwrites remote history. Coordinate with any other developers first.

---

## Alembic Migration on Render

The migration `0021_inspection_reviews` is idempotent:
- `upgrade()` checks if `inspection_reviews` table exists before creating it
- Alembic stamp advances regardless
- No data loss on re-run

If migration fails (Neon connection issue), check `DATABASE_URL` in Render dashboard.

---

## Environment Variables (Render Dashboard)

No new variables required for this deployment.  
All required vars set during initial deploy:

| Var | Backend | Frontend |
|---|---|---|
| `DATABASE_URL` | ✅ Set | — |
| `JWT_SECRET_KEY` | ✅ Generated | — |
| `CORS_ORIGINS` | ✅ Set | — |
| `DEMO_PASSWORD` | ✅ Set | — |
| `VITE_API_URL` | — | ✅ Set |
| `VITE_DEMO_MODE` | — | ✅ `true` |
