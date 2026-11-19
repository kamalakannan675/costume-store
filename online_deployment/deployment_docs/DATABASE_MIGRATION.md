# Costume Store — Database Migration & PostgreSQL Initialisation Guide

This guide covers schema provisioning, PostgreSQL migration, and catalogue importing for the online Costume Store deployment.

---

## 1. Principles of Database Separation

- **Offline Isolation**: The offline application uses an independent SQLite database (`Costume-sales/instance/costume_store.db`). It must **never** be copied, overwritten, or connected to the cloud environment.
- **Production Standard**: The online application runs on **PostgreSQL**.
- **Independent Schema Setup**: The online database schema is initialized using SQLAlchemy models (`models.py`) or the explicit catalogue migration utility (`scripts/import_catalogue.py`).

---

## 2. PostgreSQL Connection Strings

SQLAlchemy 2.x and psycopg2 require standard `postgresql://` URIs.
Hosting platforms like Render and Heroku frequently output legacy URIs starting with `postgres://`.

The application's `config.py` automatically normalizes legacy prefixes:
```text
postgres://user:pass@host/db  ──>  postgresql://user:pass@host/db
```

### SSL Considerations
Managed cloud databases (such as Render Postgres or AWS RDS) require SSL encrypted connections. Append SSL query parameters if required by your provider:
```text
postgresql://user:pass@host:5432/dbname?sslmode=require
```

---

## 3. Explicit Catalogue Import Procedure

The catalogue migration utility is located at:
`online_deployment/scripts/import_catalogue.py`

### Safety Design:
1. **Mandatory `--confirm` flag**: Prevents accidental executions.
2. **Strict Exclusions**: Never imports historical customer accounts, passwords, test orders, or payment transactions.
3. **Idempotent**: Safe to run multiple times; updates existing records and inserts missing ones without duplicating primary keys or unique slugs.

### Execution Options:

#### Option A: Running from Cloud Host Shell (e.g., Render Dashboard)
1. Open your web service dashboard on Render.
2. Navigate to the **Shell** tab.
3. Run:
   ```bash
   python scripts/import_catalogue.py --confirm
   ```

#### Option B: Running Remotely from Your Machine
If your PostgreSQL database allows external connections (Render External Connection String):
```bash
python scripts/import_catalogue.py --target-db "postgresql://user:pass@dpg-host.render.com:5432/costumedb?sslmode=require" --confirm
```

---

## 4. Verification After Import

Once the utility finishes, verify table counts:

| Table | Expected Record Count | Notes |
| :--- | :---: | :--- |
| `category` | **32** | 4 Storefront Top, 24 Subcategories, 4 Dormant |
| `costume_product` | **26** | Authentic Indian traditional attire |
| `product_variant` | **97** | Size and colour combinations with active stock |
| `product_image` | **26** | Primary gallery references |
| `coupon` | **4** | Promo discounts (`FESTIVE10`, `WELCOME50`, etc.) |
| `store_setting` | **10** | Store address, phone, delivery fee thresholds |
| `user` | **0** or **1** | Only the administrator if `ADMIN_EMAIL` was configured |
| `orders` | **0** | Clean slate, no test transactions |

---

## 5. Routine Backups & Disaster Recovery

For cloud PostgreSQL databases:
1. Enable **Automated Daily Backups** in your cloud hosting provider dashboard (Render provides 7-day retention on standard plans).
2. For manual export via `pg_dump`:
   ```bash
   pg_dump "postgresql://user:pass@host/dbname" > costume_store_online_backup.sql
   ```
3. To restore:
   ```bash
   psql "postgresql://user:pass@host/dbname" < costume_store_online_backup.sql
   ```
