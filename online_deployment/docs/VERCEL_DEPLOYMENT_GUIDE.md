# Costume Store — Vercel Production Deployment Guide

Deploying the Costume Store online application to Vercel with Neon PostgreSQL.

---

## 1. Architecture Overview

- **Hosting Platform**: Vercel Serverless Functions (Python 3.11 Runtime)
- **Framework**: Flask 3.1.0 WSGI (Native Vercel Flask Framework Detection via `app.py`)
- **Database**: Managed Serverless Neon PostgreSQL (Free Tier supported)
- **Static Assets**: Vercel Edge Global CDN via `public/` directory
- **Object Storage**: S3-Compatible Storage (AWS S3, Cloudflare R2, Supabase)
- **Payment Processing**: Razorpay (Test Mode default)
- **Source Control**: GitHub (`https://github.com/kamalakannan675/costume-store.git`, branch: `online-deployment`)

---

## 2. Prerequisites

1. A [Vercel Account](https://vercel.com/).
2. A [Neon PostgreSQL Account](https://console.neon.tech/).
3. A [GitHub Account](https://github.com/) with access to `kamalakannan675/costume-store`.
4. Razorpay Test Mode API keys.

---

## 3. Step-by-Step Vercel Deployment

### Step 1: Provision Neon PostgreSQL
Follow [NEON_DATABASE_SETUP.md](NEON_DATABASE_SETUP.md) to create your free serverless database and copy your pooled connection string (`postgresql://...@ep-...-pooler...`).

### Step 2: Import Project into Vercel
1. Log in to [Vercel Dashboard](https://vercel.com/dashboard).
2. Click **Add New...** -> **Project**.
3. Select your repository: `kamalakannan675/costume-store`.
4. In the Project Configuration screen:
   - **Framework Preset**: Automatically detected as **Flask** (or select **Flask**).
   - **Root Directory**: Click **Edit** and choose `online_deployment`.
   - **Build Command**: Leave default (empty or Vercel managed).
   - **Output Directory**: Leave default.

### Step 3: Configure Environment Variables in Vercel
Before clicking Deploy, expand **Environment Variables** in Vercel and add:

| Key | Example / Description |
| :--- | :--- |
| `FLASK_ENV` | `production` |
| `DEBUG` | `False` |
| `DATABASE_URL` | *(Your Neon PostgreSQL pooled connection string)* |
| `FLASK_SECRET_KEY` | *(Generate via `python -c "import secrets; print(secrets.token_hex(32))"`)* |
| `OTP_SECRET_KEY` | *(Generate via `python -c "import secrets; print(secrets.token_hex(32))"`)* |
| `ADMIN_EMAIL` | `admin@yourcostumestore.com` |
| `ADMIN_NAME` | `Store Administrator` |
| `ADMIN_PASSWORD` | *(Strong password: >= 8 characters, upper, lower, digit, symbol)* |
| `RAZORPAY_MODE` | `test` |
| `RAZORPAY_KEY_ID` | *(Your Razorpay Test Key ID)* |
| `RAZORPAY_KEY_SECRET` | *(Your Razorpay Test Key Secret)* |

### Step 4: Deploy
Click **Deploy**. Vercel will build your serverless function bundle in approximately 20–30 seconds.

### Step 5: Initialize Database & Import Catalogue
Follow [DATABASE_INITIALIZATION.md](DATABASE_INITIALIZATION.md) to run the one-time catalogue import utility against your Neon PostgreSQL database.

---

## 4. Verification After Deployment

1. **Health Check**:
   Visit `https://<your-vercel-domain>.vercel.app/health`.
   Verify the response:
   ```json
   {
     "status": "healthy",
     "service": "COSTUME STORE E-Commerce",
     "database": "connected"
   }
   ```
2. **Storefront Browsing**:
   Visit the homepage, check category navigation, and open `/shop`.
3. **Admin Dashboard**:
   Navigate to `/admin/login`, log in with your configured `ADMIN_EMAIL` and `ADMIN_PASSWORD`.
