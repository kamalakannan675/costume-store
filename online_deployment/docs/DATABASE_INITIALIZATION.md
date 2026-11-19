# Costume Store — Neon Database Initialisation & Catalogue Import Guide

How to initialize database schema and populate the approved 26-product Indian traditional attire catalogue into Neon PostgreSQL.

---

## 1. Safety Architecture

- **Completely Decoupled from Web Requests**: In serverless architectures like Vercel, running database initialisation during web requests is dangerous because it can cause request timeouts, cold-start delays, and concurrent migration race conditions.
- **Explicit CLI Invocation**: The import utility requires the `--confirm` flag to execute writes.
- **Strict Privacy**: Does not import test users, customer personal data, historical orders, or test reviews.
- **Idempotent**: Safe to run repeatedly without creating duplicate products or categories.

---

## 2. One-Time Execution Procedure

Execute the import script from your local development machine pointing directly to your Neon database:

### Command:
```bash
python scripts/import_catalogue.py --target-db "postgresql://neondb_owner:YourPassword@ep-xyz-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require" --confirm
```

### What Happens:
1. **Schema Generation**: SQLAlchemy executes `db.create_all()` against Neon PostgreSQL to create all 17 relational tables.
2. **Category Population**: Imports 32 categories (storefront and dormant).
3. **Product & Variant Population**: Imports the 26 approved traditional Indian products and their 97 size/colour variants.
4. **Gallery Images**: Links all 26 primary product image paths.
5. **Coupons & Settings**: Configures 4 discount coupons and 10 default store settings.

---

## 3. Post-Import Verification

The script automatically reports verified database counts upon completion:

| Entity | Verified Count |
| :--- | :---: |
| Storefront Categories | **32** |
| Active Products | **26** |
| Product Variants | **97** |
| Primary Image Records | **26** |
| Active Coupons | **4** |
| Store Settings | **10** |
| User Accounts | **0** (or 1 if admin configured) |
| Orders | **0** |

---

## 4. Troubleshooting Neon Connectivity

- **SSL Required**: Ensure `?sslmode=require` is present at the end of the connection string.
- **PgBouncer Pooling**: Always use the `-pooler` hostname provided in the Neon console.
- **Firewall**: Neon databases accept connections over port 5432 with standard SSL encryption.
