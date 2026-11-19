# Costume Store — Vercel Production Deployment Checklist

Pre-flight and post-deployment checklist for launching the Costume Store online application on Vercel with Neon PostgreSQL.

---

## 1. Neon Database Setup
- [ ] Created Neon project (`costume-store-db`).
- [ ] Copied Pooled Connection String (`-pooler`).
- [ ] Confirmed `?sslmode=require` is present in the URI.
- [ ] Executed catalogue import via protected environment variable (`TARGET_DATABASE_URL="<neon-uri>"` + `python scripts/import_catalogue.py --confirm`).
- [ ] Verified table counts: 32 categories, 26 products, 97 variants.

---

## 2. Security & Credentials
- [ ] Generated 32-character high-entropy `FLASK_SECRET_KEY`.
- [ ] Generated 32-character high-entropy `OTP_SECRET_KEY`.
- [ ] Verified `FLASK_ENV=production` and `DEBUG=False`.
- [ ] Confirmed no real secrets or `.env` files are tracked in Git.

---

## 3. Vercel Configuration
- [ ] Connected repository `kamalakannan675/costume-store`.
- [ ] Selected branch: `online-deployment`.
- [ ] Configured Root Directory: `online_deployment`.
- [ ] Framework preset detected as **Flask** via native `app.py` entrypoint.
- [ ] Confirmed static assets are served from `public/` directory via Vercel Edge CDN.
- [ ] Confirmed no legacy `api/index.py` or catch-all rewrites are required.
- [ ] Added all required environment variables in Vercel Project Settings.

---

## 4. Payment Gateway (Razorpay)
- [ ] Verified `RAZORPAY_MODE=test` (for initial launch).
- [ ] Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.
- [ ] Configured Webhook endpoint: `https://<your-vercel-domain>.vercel.app/webhook/razorpay`.

---

## 5. Post-Deployment Live Verification
- [ ] Checked `GET /health` returns `200 OK` with `{"status": "healthy", "database": "connected"}`.
- [ ] Verified Homepage loads with featured traditional attire categories.
- [ ] Verified `/shop` catalogue loads all 26 Indian products with images, prices, and variant selectors.
- [ ] Verified customer registration and login.
- [ ] Verified shopping bag addition and quantity updates.
- [ ] Verified checkout flow.
- [ ] Verified admin login at `/admin/login` and dashboard analytics at `/admin/dashboard`.
