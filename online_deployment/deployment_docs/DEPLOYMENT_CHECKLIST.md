# Costume Store — Pre-Flight Production Deployment Checklist

Use this checklist before and during deploying the Costume Store online application to a cloud host (such as Render, Heroku, AWS, or Railway).

---

## 1. Security & Cryptographic Secrets
- [ ] **Cryptographic Secret Key**: Generated high-entropy 32-byte secret using `secrets.token_hex(32)`.
- [ ] **OTP Secret Key**: Generated independent 32-byte secret for transactional verification.
- [ ] **Debug Mode Disabled**: Confirmed `DEBUG=False` and `FLASK_ENV=production`.
- [ ] **Secure Cookies**: Confirmed `SESSION_COOKIE_SECURE=True` is active for HTTPS environments.
- [ ] **Zero Hardcoded Secrets**: Scanned repository to ensure no `.env` file, database passwords, or private keys are committed.

---

## 2. PostgreSQL Database Provisioning
- [ ] **PostgreSQL Instance**: Created managed PostgreSQL 14+ instance.
- [ ] **DATABASE_URL Configured**: Stored full connection string in the cloud hosting dashboard (`postgresql://user:pass@host:5432/dbname`).
- [ ] **SSL Connectivity**: Ensured connection parameters support SSL if mandated by the host (`sslmode=require`).
- [ ] **Connection Pooling**: Verified SQLAlchemy engine options recycle connections safely (`pool_pre_ping=True`).

---

## 3. Catalogue Import & Database Initialisation
- [ ] **Manual Import Invocation**: Executed `python scripts/import_catalogue.py --confirm` via the hosting shell or pre-deploy job.
- [ ] **Verified Category Count**: Exactly 32 categories (storefront and dormant) present.
- [ ] **Verified Product Count**: Exactly 26 approved traditional Indian products present.
- [ ] **Verified Variant Count**: Exactly 97 size/colour variants present with active stock.
- [ ] **No Account Leakage**: Confirmed 0 historical customer records, test orders, or test reviews were imported.

---

## 4. Primary Administrator Setup
- [ ] **ADMIN_EMAIL Set**: Configured intended production store administrator email.
- [ ] **ADMIN_NAME Set**: Configured display name.
- [ ] **ADMIN_PASSWORD Set**: Configured complex password (>= 8 characters, upper, lower, digit, symbol).
- [ ] **Login Verification**: Logged in at `/admin/login` and verified redirection to `/admin/dashboard`.

---

## 5. Persistent Media Storage (S3 / Cloudflare R2)
- [ ] **Storage Mode Evaluated**: Decided between `STORAGE_BACKEND=local` (with persistent disk mount) and `STORAGE_BACKEND=s3` (S3/R2/Supabase).
- [ ] **S3 Credentials (if enabled)**:
  - `S3_BUCKET_NAME`
  - `S3_REGION_NAME`
  - `S3_ACCESS_KEY_ID`
  - `S3_SECRET_ACCESS_KEY`
- [ ] **Static Assets Check**: Confirmed that bundled catalog images (`/static/images/products/...`) load from static bundle.

---

## 6. Payment Processing (Razorpay)
- [ ] **Initial Mode**: Verified `RAZORPAY_MODE=test` for end-to-end rehearsal before public launch.
- [ ] **Credentials Configured**: Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.
- [ ] **Webhook Endpoint**: Registered `https://<your-domain>/webhook/razorpay` in the Razorpay Dashboard.
- [ ] **Webhook Secret**: Stored secret in `RAZORPAY_WEBHOOK_SECRET`.
- [ ] **Live Activation Planned**: Followed `RAZORPAY_LIVE_ACTIVATION.md` for post-KYC live activation.

---

## 7. Transactional Email & Notifications
- [ ] **SMTP Provider Configured**: Set `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`.
- [ ] **Default Sender**: Set `MAIL_DEFAULT_SENDER` to a verified branded domain address.
- [ ] **Admin Alerts**: Configured `MAIL_ADMIN_NOTIFICATION_EMAIL` to receive new order alerts.
- [ ] **Enable Flag**: Set `MAIL_ENABLED=True` once credentials are verified.

---

## 8. Post-Deployment Verification
- [ ] **Health Endpoint**: Checked `https://<your-domain>/health` returns `{"status": "healthy", "database": "connected"}`.
- [ ] **Storefront Browsing**: Checked homepage, catalog browsing (`/shop`), search, and filters.
- [ ] **Cart Flow**: Tested adding an item to bag, updating quantity, applying coupon `FESTIVE10`.
- [ ] **Checkout Flow**: Tested placing an order via Cash on Delivery.
- [ ] **Admin Sales Dashboard**: Verified order appears in admin dashboard with correct revenue accounting.
