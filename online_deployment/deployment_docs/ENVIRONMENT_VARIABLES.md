# Costume Store — Production Environment Variables Specification

This document details all environment variables supported by the online deployment codebase.

---

## 1. Core Framework & Security

| Variable Name | Required | Default | Description | Example / Recommendations |
| :--- | :---: | :---: | :--- | :--- |
| `FLASK_ENV` | **Yes** | `production` | Deployment environment mode. | `production` |
| `DEBUG` | **Yes** | `False` | Disables interactive debuggers and traceback exposure. | `False` |
| `FLASK_SECRET_KEY` | **Yes** | *(None)* | Cryptographic key for session signing and CSRF tokens. Minimum 32 chars. | `c8f1e29d4a8b7c6e5f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e` |
| `OTP_SECRET_KEY` | **Yes** | *(None)* | Secret key for generating and validating one-time passwords. | `7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b` |
| `SESSION_COOKIE_SECURE`| No | `True` | Restricts cookies to HTTPS traffic only. | `True` (Mandatory for production HTTPS) |
| `SESSION_COOKIE_HTTPONLY`| No | `True` | Prevents client JavaScript from reading session cookies. | `True` |
| `SESSION_COOKIE_SAMESITE`| No | `Lax` | Mitigates CSRF vulnerabilities across cross-site requests. | `Lax` |

---

## 2. Database Connectivity

| Variable Name | Required | Default | Description | Example / Recommendations |
| :--- | :---: | :---: | :--- | :--- |
| `DATABASE_URL` | **Yes** | *(None)* | PostgreSQL connection URL. Automatically converts `postgres://` to `postgresql://`. | `postgresql://costume_usr:SecretPwd@dpg-host.render.com/costumedb` |
| `AUTO_CREATE_TABLES`| No | `False` | Whether application startup executes `db.create_all()` in production. | `False` (Recommended to use `import_catalogue.py`) |

---

## 3. Store Administrator Provisioning

| Variable Name | Required | Default | Description | Example / Recommendations |
| :--- | :---: | :---: | :--- | :--- |
| `ADMIN_EMAIL` | Optional | *(None)* | Email address of the primary administrator account. | `admin@costumestore.com` |
| `ADMIN_NAME` | Optional | `Store Administrator` | Display name of the administrator. | `Kamalakannan R` |
| `ADMIN_PASSWORD` | Optional | *(None)* | Complex initial password (min 8 chars, uppercase, lowercase, digit, symbol). | `Admin@Costume2026!` |

---

## 4. Payment Gateway (Razorpay)

| Variable Name | Required | Default | Description | Example / Recommendations |
| :--- | :---: | :---: | :--- | :--- |
| `RAZORPAY_MODE` | No | `test` | Operating gateway mode: `test` or `live`. | `test` (Switch to `live` after activation) |
| `RAZORPAY_KEY_ID` | Optional | `""` | Razorpay Key ID generated in the Razorpay Dashboard. | `rzp_test_...` or `rzp_live_...` |
| `RAZORPAY_KEY_SECRET` | Optional | `""` | Razorpay Key Secret for HMAC-SHA256 signature verification. | `AbCdEf123456...` |
| `RAZORPAY_WEBHOOK_SECRET`| Optional | `""` | Secret configured on `/webhook/razorpay` for webhook verification. | `whsec_...` |

---

## 5. Persistent Cloud Media Storage

| Variable Name | Required | Default | Description | Example / Recommendations |
| :--- | :---: | :---: | :--- | :--- |
| `STORAGE_BACKEND` | No | `local` | Storage provider: `local` or `s3`. | `local` (Render Disks) or `s3` (AWS / R2) |
| `S3_BUCKET_NAME` | S3 only | `""` | Name of the cloud object storage bucket. | `costume-store-media` |
| `S3_REGION_NAME` | S3 only | `us-east-1` | AWS or provider region. | `ap-south-1` (Mumbai) or `auto` (R2) |
| `S3_ACCESS_KEY_ID` | S3 only | `""` | IAM or API access key for object storage. | `YOUR_S3_ACCESS_KEY_ID` |
| `S3_SECRET_ACCESS_KEY`| S3 only | `""` | IAM or API secret key for object storage. | `YOUR_S3_SECRET_ACCESS_KEY` |
| `S3_ENDPOINT_URL` | S3 only | *(None)* | Custom endpoint for non-AWS S3 (Cloudflare R2, MinIO, Wasabi, Supabase). | `https://<accountid>.r2.cloudflarestorage.com` |
| `S3_PUBLIC_URL_PREFIX`| S3 only | *(None)* | Public CDN or custom domain URL prefix for uploaded media. | `https://media.costumestore.com` |

---

## 6. Transactional Email & Notifications (SMTP)

| Variable Name | Required | Default | Description | Example / Recommendations |
| :--- | :---: | :---: | :--- | :--- |
| `MAIL_ENABLED` | No | `False` | Master switch for dispatching transactional emails. | `True` |
| `MAIL_SERVER` | If enabled | `smtp.gmail.com` | SMTP relay server hostname. | `smtp.sendgrid.net`, `smtp.mailgun.org`, `smtp.gmail.com` |
| `MAIL_PORT` | If enabled | `587` | SMTP relay port (587 for TLS, 465 for SSL). | `587` |
| `MAIL_USE_TLS` | If enabled | `True` | Enforce STARTTLS encryption. | `True` |
| `MAIL_USE_SSL` | If enabled | `False` | Enforce SSL encryption. | `False` |
| `MAIL_USERNAME` | If enabled | `""` | SMTP authentication username. | `apikey` or `notifications@costumestore.com` |
| `MAIL_PASSWORD` | If enabled | `""` | SMTP authentication token or application password. | *(Your SendGrid/Google App Password)* |
| `MAIL_DEFAULT_SENDER`| If enabled | `""` | `From:` address on customer order emails. | `Costume Store <orders@costumestore.com>` |
| `MAIL_ADMIN_NOTIFICATION_EMAIL`| No | `""` | Destination address for internal new-order notifications. | `operations@costumestore.com` |
