# Costume Store — Neon Database Initialization & Catalogue Import Guide

How to initialize database schema, populate the approved 26-product Indian traditional attire catalogue, and provision administrator access in Neon PostgreSQL.

---

## 1. Safety Architecture

- **Completely Decoupled from Web Traffic by Default**: Automatic schema creation on every serverless invocation is disabled by default to prevent latency and race conditions.
- **Idempotent**: Safe to run repeatedly without creating duplicate products, variants, or categories.
- **Strict Privacy**: Does not import customer accounts, customer addresses, orders, or transactions.
- **Offline Protection**: Strictly validates that operations never target or modify the offline SQLite database (`instance/costume_store.db`).
- **Credential Masking**: Automatically masks database passwords and connection strings in all logs and console output.

---

## 2. Supported Execution Methods

### Method 1: Local / CI CLI Execution (Recommended)

Set the connection string as a temporary session environment variable (`TARGET_DATABASE_URL`) to avoid exposing credentials in shell history.

#### Windows (PowerShell):
```powershell
# 1. Set the environment variable for the current session
$env:TARGET_DATABASE_URL="postgresql://neondb_owner:YourPassword@ep-xyz-pooler.region.aws.neon.tech/neondb?sslmode=require"

# 2. Inspect target database without writing (Dry Run)
python scripts/import_catalogue.py --check

# 3. Execute schema creation and catalogue import
python scripts/import_catalogue.py --confirm

# 4. Clean up session environment variable
Remove-Item Env:\TARGET_DATABASE_URL
```

#### Linux / macOS (Bash / Zsh):
```bash
# 1. Export the environment variable for the session
export TARGET_DATABASE_URL="postgresql://neondb_owner:YourPassword@ep-xyz-pooler.region.aws.neon.tech/neondb?sslmode=require"

# 2. Inspect target database without writing (Dry Run)
python scripts/import_catalogue.py --check

# 3. Execute schema creation and catalogue import
python scripts/import_catalogue.py --confirm

# 4. Clean up session environment variable
unset TARGET_DATABASE_URL
```

---

### Method 2: Automatic One-Time Startup Initialization (Vercel Console)

If you prefer Vercel to initialize Neon directly on deployment:

1. Open your project on the [Vercel Dashboard](https://vercel.com/).
2. Navigate to **Settings** → **Environment Variables**.
3. Add or update:
   - `AUTO_CREATE_TABLES` = `true`
4. Redeploy or trigger any request (e.g., `GET https://costume-store-beryl.vercel.app/health`).
5. Vercel executes `db.create_all()` and seeds the 26-product catalogue and store settings on initial boot.
6. Once `/health` reports `status: "healthy"`, you can safely set `AUTO_CREATE_TABLES` = `false`.

---

### Method 3: Remote Maintenance API (One-Click HTTP)

If your application is already deployed on Vercel with `FLASK_SECRET_KEY` configured:

Execute a secure POST request to the maintenance endpoint:
```bash
curl -X POST https://costume-store-beryl.vercel.app/api/maintenance/init-database \
     -H "X-Maintenance-Secret: YOUR_FLASK_SECRET_KEY"
```

Response payload:
```json
{
  "status": "success",
  "message": "Database schema and catalogue initialized successfully.",
  "counts": {
    "categories": 32,
    "active_products": 26,
    "variants": 97,
    "images": 26,
    "coupons": 4,
    "store_settings": 10,
    "admin_provisioned": true
  }
}
```

---

## 3. Verified Post-Import State

Upon completion, the Neon database contains:

| Entity | Target Verified Count | Description |
| :--- | :---: | :--- |
| **Relational Tables** | **17** | All SQLAlchemy models mapped |
| **Storefront Categories** | **32** | 4 primary roots + 28 subcategories |
| **Active Products** | **26** | Authentic Indian traditional attire catalogue |
| **Product Variants** | **97** | Sizes, colours, and inventory counts |
| **Gallery Images** | **26** | Root-relative edge CDN image paths |
| **Discount Coupons** | **4** | Active festive discount codes |
| **Store Settings** | **10** | Default store branding and policies |
| **User Accounts** | **1** | Primary administrator (if configured in env) |
| **Customer Orders** | **0** | Clean production state |

---

## 4. Verification Endpoint

Query the readiness check:
```bash
curl https://costume-store-beryl.vercel.app/health
```
When fully initialized, the endpoint returns **HTTP 200 OK**:
```json
{
  "service": "COSTUME STORE E-Commerce",
  "status": "healthy",
  "database": "connected",
  "checks": {
    "database_connection": "connected",
    "schema_initialized": true,
    "catalogue_ready": true,
    "table_count": 17,
    "categories_count": 32,
    "active_products_count": 26
  }
}
```
If schema tables are missing, the endpoint returns **HTTP 503**:
```json
{
  "service": "COSTUME STORE E-Commerce",
  "status": "degraded_schema_missing",
  "database": "connected",
  "checks": {
    "database_connection": "connected",
    "schema_initialized": false,
    "catalogue_ready": false,
    "table_count": 0,
    "missing_tables": ["user", "address", "category", "..."]
  }
}
```
