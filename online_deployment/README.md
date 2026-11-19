# Costume Store — Online Deployment & Cloud Production Architecture

A modern, full-featured Flask and PostgreSQL e-commerce platform specializing in authentic Indian traditional attire and cultural costumes.

---

## 1. System Overview & Architecture

- **Web Framework**: Flask 3.1.0 (Python 3.11+)
- **WSGI Application Server**: Gunicorn 21.2.0 (4 worker processes recommended)
- **Database (Production)**: Managed PostgreSQL (Render Postgres, Supabase, Neon, AWS RDS)
- **Database (Development)**: Independent SQLite (`instance/costume_store.db`)
- **Object-Relational Mapping**: Flask-SQLAlchemy 3.1.1
- **Payment Processing**: Razorpay Payment Gateway (Test Mode default; Live Mode ready)
- **Persistent Media Storage**: Dual-mode storage engine (`LocalStorage` for dev, `S3Storage` for S3/R2/Wasabi/Supabase in production)
- **Transactional Communications**: SMTP email engine with mock fallbacks in development and automated testing
- **Address Intelligence**: India Post official postal database covering 36 States/UTs, 782 districts, and 19,295 PIN codes

---

## 2. Directory Structure

```text
online_deployment/
├── .env.example                    # Clean production environment template
├── .gitignore                      # Strict Git exclusions (no secrets, databases, or local media)
├── Procfile                        # Render & Heroku process definition (gunicorn)
├── README.md                       # Main architecture & developer documentation
├── render.yaml                     # Render infrastructure Blueprint
├── requirements.txt                # Production dependencies
├── run.py                          # Local development server entrypoint
├── app.py                          # Application factory, routes, and WSGI entrypoint
├── config.py                       # Multi-environment configuration & validation
├── models.py                       # SQLAlchemy relational schema (17 tables)
├── storage_service.py              # Cloud & local file persistence abstraction
├── sales_service.py                # Sales analytics, financial accounting & report generation
├── email_service.py                # Transactional email & OTP delivery
├── india_locations.py              # Indian address validation & heuristics
├── deployment_docs/                # Dedicated operational manuals
│   ├── DATABASE_MIGRATION.md       # PostgreSQL schema setup & catalogue import
│   ├── DEPLOYMENT_CHECKLIST.md     # Pre-flight production deployment steps
│   ├── ENVIRONMENT_VARIABLES.md    # Exhaustive environment variable specification
│   └── RAZORPAY_LIVE_ACTIVATION.md # Razorpay live mode switchover instructions
├── scripts/
│   ├── import_catalogue.py         # Explicit, idempotent catalogue import utility
│   ├── init_db.py                  # Local database schema initialisation
│   └── seed_database.py            # Canonical 26-product Indian catalogue definition
├── static/                         # CSS, JavaScript, fonts, and catalog assets
│   ├── css/                        # Responsive e-commerce styling
│   ├── js/                         # Client validation & cascading address dropdowns
│   ├── images/                     # 26 approved traditional Indian product images
│   └── uploads/                    # Dynamic upload mount directory
├── templates/                      # Jinja2 HTML responsive templates
└── tests/                          # Independent deployment test suite
    └── test_online_deployment.py   # 16 automated tests covering all 22 deployment requirements
```

---

## 3. Local Development (Online Codebase)

1. **Clone & Setup Virtual Environment**:
   ```bash
   cd online_deployment
   python -m venv .venv
   source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Local Environment**:
   ```bash
   cp .env.example .env
   ```
   Fill in minimum keys in `.env`:
   ```env
   FLASK_SECRET_KEY=dev-costume-store-local-secret-32-chars-hex!
   OTP_SECRET_KEY=dev-costume-store-local-otp-secret-32chars!
   FLASK_ENV=development
   DEBUG=True
   ```

3. **Start Local Server**:
   ```bash
   python run.py
   ```
   Access at `http://127.0.0.1:5000/`.

---

## 4. Production Deployment on Render

### Step 1: Create Managed PostgreSQL
1. Log in to the [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** -> **PostgreSQL**.
3. Name: `costume-store-postgres`.
4. Copy the **Internal Database URL**.

### Step 2: Create Web Service
1. Click **New +** -> **Web Service**.
2. Connect your Git repository (`https://github.com/kamalakannan675/costume-store.git`).
3. Set **Root Directory**: `online_deployment`.
4. Runtime: `Python 3`.
5. Build Command: `pip install -r requirements.txt`.
6. Start Command: `gunicorn -w 4 -b 0.0.0.0:$PORT "app:app"`.

### Step 3: Configure Environment Variables
In the Render Web Service settings, add the required environment variables:
- `FLASK_ENV`: `production`
- `DEBUG`: `False`
- `DATABASE_URL`: *(Your Render PostgreSQL connection string)*
- `FLASK_SECRET_KEY`: *(Generate using `python -c "import secrets; print(secrets.token_hex(32))"`)*
- `OTP_SECRET_KEY`: *(Generate using `python -c "import secrets; print(secrets.token_hex(32))"`)*
- `ADMIN_EMAIL`: `admin@yourstore.com`
- `ADMIN_NAME`: `Store Administrator`
- `ADMIN_PASSWORD`: *(A strong password with >= 8 chars, uppercase, lowercase, digit, symbol)*
- `RAZORPAY_MODE`: `test` (or `live` when activated)
- `RAZORPAY_KEY_ID`: *(Your Razorpay Key ID)*
- `RAZORPAY_KEY_SECRET`: *(Your Razorpay Key Secret)*

### Step 4: Import Catalogue to PostgreSQL
Once the Web Service is deployed:
1. Open the **Shell** tab in the Render Dashboard for your Web Service.
2. Run the explicit catalogue import utility:
   ```bash
   python scripts/import_catalogue.py --confirm
   ```
3. This creates all schema tables and imports all 32 categories, 26 products, 97 variants, 26 images, 4 coupons, and 10 store settings without creating dummy user accounts or orders.

---

## 5. Health Monitoring & Verification

Render health check is built-in:
- **Endpoint**: `GET /health`
- **Response**:
  ```json
  {
    "status": "healthy",
    "service": "COSTUME STORE E-Commerce",
    "database": "connected",
    "timestamp": "2026-11-19T13:30:00.000000"
  }
  ```

---

## 6. Testing

Run the isolated deployment test suite:
```bash
python -m unittest tests/test_online_deployment.py
```
*All 16 tests execute in under 3 seconds using isolated in-memory or ephemeral databases.*
