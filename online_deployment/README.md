# Costume Store — Vercel & Neon PostgreSQL Deployment Architecture

A modern, high-performance, full-featured Flask and Neon PostgreSQL e-commerce platform specializing in authentic Indian traditional attire and cultural costumes.

---

## 1. System Overview & Architecture

- **Web Framework**: Flask 3.1.0 (Python 3.11+)
- **Serverless Runtime**: Vercel Serverless Functions (`api/index.py` WSGI entrypoint)
- **Database (Production)**: Managed Serverless Neon PostgreSQL with PgBouncer connection pooling
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
├── README.md                       # Main architecture & developer documentation
├── vercel.json                     # Vercel configuration & rewrite rules
├── requirements.txt                # Production dependencies
├── run.py                          # Local development server entrypoint
├── app.py                          # Application factory, routes, and WSGI entrypoint
├── config.py                       # Multi-environment configuration & validation
├── models.py                       # SQLAlchemy relational schema (17 tables)
├── storage_service.py              # Cloud & local file persistence abstraction
├── sales_service.py                # Sales analytics, financial accounting & report generation
├── email_service.py                # Transactional email & OTP delivery
├── india_locations.py              # Indian address validation & heuristics
├── api/
│   └── index.py                    # Vercel Serverless Function entrypoint exposing 'app'
├── docs/                           # Dedicated operational manuals
│   ├── VERCEL_DEPLOYMENT_GUIDE.md  # Comprehensive step-by-step Vercel guide
│   ├── NEON_DATABASE_SETUP.md      # Neon PostgreSQL provisioning & pooling guide
│   ├── VERCEL_ENVIRONMENT_VARIABLES.md # Complete environment variable reference
│   ├── DATABASE_INITIALIZATION.md  # PostgreSQL schema setup & catalogue import
│   └── PRODUCTION_DEPLOYMENT_CHECKLIST.md # Pre-flight production checklist
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
    └── test_online_deployment.py   # Automated tests covering Vercel, Neon, and all core flows
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

## 4. Production Deployment on Vercel

Follow the step-by-step guide in [docs/VERCEL_DEPLOYMENT_GUIDE.md](docs/VERCEL_DEPLOYMENT_GUIDE.md):

1. **Provision Database**: Create a project in [Neon Console](https://console.neon.tech/) and copy the pooled connection string.
2. **Import Project into Vercel**: Connect repository `kamalakannan675/costume-store`, branch `online-deployment`, root directory `online_deployment`.
3. **Configure Environment Variables**: Add `DATABASE_URL`, `FLASK_SECRET_KEY`, `OTP_SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and Razorpay keys in Vercel Project Settings.
4. **Deploy**: Click Deploy.
5. **Import Catalogue**: Run `python scripts/import_catalogue.py --target-db "<neon-uri>" --confirm` from your local environment to seed the 26 approved products into Neon.

---

## 5. Health Monitoring & Verification

- **Endpoint**: `GET /health`
- **Response**:
  ```json
  {
    "status": "healthy",
    "service": "COSTUME STORE E-Commerce",
    "database": "connected",
    "timestamp": "2026-11-19T14:30:00.000000"
  }
  ```

---

## 6. Testing

Run the isolated deployment test suite:
```bash
python -m unittest tests/test_online_deployment.py
```
*All tests execute using isolated in-memory or ephemeral databases.*
