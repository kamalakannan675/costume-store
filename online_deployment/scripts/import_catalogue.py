r"""
COSTUME STORE — Neon Production Database Schema Initialization & Catalogue Import Utility
Explicitly invoked standalone utility to initialize schema tables, seed the approved catalogue,
and synchronize administrator credentials into Neon PostgreSQL.

Includes:
  - 17 Relational Schema Tables
  - 32 Categories (hierarchy preserved)
  - 26 Approved Indian traditional products
  - 97 Product variants (sizes, colours, stock counts)
  - 26 Product image records
  - 4 Discount coupons
  - 10 Store settings
  - Primary Administrator account (from ADMIN_EMAIL / ADMIN_PASSWORD if provided)

Explicitly EXCLUDES:
  - Customer personal accounts
  - Customer addresses and payment details
  - Historical customer orders and order items
  - Payment transactions
  - Customer reviews and wishlist entries

Usage (Protected Session Environment Variable):
  # Linux / macOS / Bash:
  export TARGET_DATABASE_URL="postgresql://user:pass@ep-name-pooler.region.aws.neon.tech/neondb?sslmode=require"
  python scripts/import_catalogue.py --check
  python scripts/import_catalogue.py --confirm
  unset TARGET_DATABASE_URL

  # Windows PowerShell:
  $env:TARGET_DATABASE_URL="postgresql://user:pass@ep-name-pooler.region.aws.neon.tech/neondb?sslmode=require"
  python scripts/import_catalogue.py --check
  python scripts/import_catalogue.py --confirm
  Remove-Item Env:\TARGET_DATABASE_URL
"""

import os
import sys
import argparse
from sqlalchemy import inspect, text

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

REQUIRED_TABLES = [
    'user', 'address', 'category', 'costume_product', 'product_image',
    'product_variant', 'coupon', 'orders', 'order_status_log', 'otp_token',
    'order_item', 'wishlist', 'product_review', 'store_setting',
    'payment_transaction', 'contact_message', 'inventory_restock_log'
]


def mask_connection_url(url: str) -> str:
    """Mask credentials in database connection URLs for safe logging."""
    if not url:
        return "(empty)"
    if '@' in url and '://' in url:
        prefix, rest = url.split('://', 1)
        creds, host_part = rest.split('@', 1)
        user = creds.split(':')[0]
        return f"{prefix}://{user}:****@{host_part}"
    return url


def validate_target_url_safety(target_url: str):
    """Refuse to execute against the offline SQLite database."""
    if not target_url:
        raise ValueError("No database URL provided. Set TARGET_DATABASE_URL or DATABASE_URL.")
    
    clean_lower = target_url.lower().replace('\\', '/')
    if 'sqlite' in clean_lower:
        if 'costume_store.db' in clean_lower or 'instance' in clean_lower:
            raise RuntimeError(
                "[CRITICAL SECURITY REFUSAL] Refusing to run import against offline SQLite database! "
                "TARGET_DATABASE_URL must point to your production Neon PostgreSQL database."
            )


def check_database_status(target_db_url: str = None):
    """Dry-run inspection of target database connection, existing tables, and catalogue counts."""
    effective_url = target_db_url or os.environ.get('TARGET_DATABASE_URL') or os.environ.get('DATABASE_URL')
    validate_target_url_safety(effective_url)

    from config import normalize_database_url
    from app import app
    from models import db, Category, Product, ProductVariant, ProductImage, Coupon, StoreSetting, User

    app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_url(effective_url)
    display_url = mask_connection_url(app.config['SQLALCHEMY_DATABASE_URI'])

    print("=" * 70)
    print("COSTUME STORE — TARGET DATABASE STATUS INSPECTION")
    print("=" * 70)
    print(f"Target Database : {display_url}")
    print("=" * 70)

    with app.app_context():
        # 1. Connectivity test
        try:
            db.session.execute(text('SELECT 1'))
            print("[✓] Database Connection: SUCCESSFUL (SELECT 1 passed)")
        except Exception as e:
            print(f"[✗] Database Connection FAILED: {e}")
            return False

        # 2. Table inspection
        inspector = inspect(db.engine)
        existing = set(inspector.get_table_names())
        missing = [t for t in REQUIRED_TABLES if t not in existing]

        print(f"\n[Schema Inspection]")
        print(f"  -> Total Tables Present : {len(existing)}")
        print(f"  -> Required Tables (17) : {len(REQUIRED_TABLES) - len(missing)}/17 present")
        if missing:
            print(f"  -> Missing Tables       : {', '.join(missing)}")
        else:
            print(f"  -> All 17 required application tables are PRESENT.")

        # 3. Record counts if tables exist
        if 'category' in existing and 'costume_product' in existing:
            cat_count = Category.query.count()
            prod_count = Product.query.count()
            var_count = ProductVariant.query.count() if 'product_variant' in existing else 0
            img_count = ProductImage.query.count() if 'product_image' in existing else 0
            coup_count = Coupon.query.count() if 'coupon' in existing else 0
            admin_count = User.query.filter_by(is_admin=True).count() if 'user' in existing else 0

            print(f"\n[Catalogue Data Inspection]")
            print(f"  -> Categories       : {cat_count} (Expected: 32)")
            print(f"  -> Products         : {prod_count} (Expected: 26)")
            print(f"  -> Variants         : {var_count} (Expected: 97)")
            print(f"  -> Images           : {img_count} (Expected: 26)")
            print(f"  -> Coupons          : {coup_count} (Expected: 4)")
            print(f"  -> Admin Accounts   : {admin_count}")
        else:
            print("\n[Catalogue Data Inspection]")
            print("  -> Schema not initialized yet. Run with --confirm to create tables and import catalogue.")

        print("=" * 70)
        return True


def run_catalogue_import(target_db_url: str = None):
    """Imports schema and catalogue idempotently into the target database."""
    effective_url = target_db_url or os.environ.get('TARGET_DATABASE_URL') or os.environ.get('DATABASE_URL')
    validate_target_url_safety(effective_url)

    from config import normalize_database_url
    from app import app, sync_admin_from_env
    from models import db, Category, Product, ProductVariant, ProductImage, Coupon, StoreSetting, User
    from scripts.seed_database import seed_database

    app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_url(effective_url)
    display_url = mask_connection_url(app.config['SQLALCHEMY_DATABASE_URI'])

    print("=" * 70)
    print("COSTUME STORE — PRODUCTION NEON DATABASE INITIALIZATION & IMPORT")
    print("=" * 70)
    print(f"Target Database : {display_url}")
    print("=" * 70)

    with app.app_context():
        # Test connection
        try:
            db.session.execute(text('SELECT 1'))
            print("[✓] Connectivity verified.")
        except Exception as e:
            print(f"[✗] Connection failed: {e}")
            sys.exit(1)

        # Baseline count before import
        inspector = inspect(db.engine)
        existing_tables_before = set(inspector.get_table_names())
        cat_before = Category.query.count() if 'category' in existing_tables_before else 0
        prod_before = Product.query.count() if 'costume_product' in existing_tables_before else 0
        var_before = ProductVariant.query.count() if 'product_variant' in existing_tables_before else 0
        img_before = ProductImage.query.count() if 'product_image' in existing_tables_before else 0
        coup_before = Coupon.query.count() if 'coupon' in existing_tables_before else 0

        # Step 1: Schema creation
        print("\n[Step 1/3] Ensuring 17 relational schema tables exist in target database...")
        db.create_all()

        inspector_after = inspect(db.engine)
        existing_tables_after = set(inspector_after.get_table_names())
        tables_created = len(existing_tables_after) - len(existing_tables_before)
        print(f"  -> Total tables now present: {len(existing_tables_after)}/17 (Newly created: {max(0, tables_created)})")

        # Step 2: Seed catalogue (Idempotent lookup-before-insert)
        print("\n[Step 2/3] Seeding approved 26-product Indian traditional attire catalogue...")
        seed_database()

        cat_after = Category.query.count()
        prod_after = Product.query.filter_by(is_active=True).count()
        var_after = ProductVariant.query.filter_by(is_active=True).count()
        img_after = ProductImage.query.count()
        coup_after = Coupon.query.count()
        set_after = StoreSetting.query.count()

        print("\n[Import & Idempotency Audit Summary]")
        print(f"  -> Storefront Categories : Added: {cat_after - cat_before}, Preserved/Existing: {cat_before}, Total: {cat_after} (Expected: 32)")
        print(f"  -> Active Products       : Added: {prod_after - prod_before}, Preserved/Existing: {prod_before}, Total: {prod_after} (Expected: 26)")
        print(f"  -> Product Variants      : Added: {var_after - var_before}, Preserved/Existing: {var_before}, Total: {var_after} (Expected: 97)")
        print(f"  -> Gallery Images        : Added: {img_after - img_before}, Preserved/Existing: {img_before}, Total: {img_after} (Expected: 26)")
        print(f"  -> Discount Coupons      : Added: {coup_after - coup_before}, Preserved/Existing: {coup_before}, Total: {coup_after} (Expected: 4)")
        print(f"  -> Store Settings        : Total active: {set_after} (Expected: 10)")
        print(f"  -> Total Categories:      {cat_after} (Expected: 32)")
        print(f"  -> Total Active Products: {prod_after} (Expected: 26)")
        print(f"  -> Total Active Variants: {var_after} (Expected: 97)")
        print(f"  -> Total Images:          {img_after} (Expected: 26)")
        print(f"  -> Total Coupons:         {coup_after} (Expected: 4)")
        print(f"  -> Total Store Settings:  {set_after} (Expected: 10)")

        # Step 3: Admin account synchronization
        print("\n[Step 3/3] Synchronizing store administrator account from environment...")
        admin = sync_admin_from_env(app)
        if admin:
            print(f"  -> Primary Administrator : Verified ({admin.email})")
        else:
            print("  -> Primary Administrator : Deferred (ADMIN_EMAIL / ADMIN_PASSWORD not set in current session).")

        print("\n" + "=" * 70)
        print("DATABASE INITIALIZATION & CATALOGUE IMPORT COMPLETED SUCCESSFULLY!")
        print("Zero customer accounts, customer addresses, orders, or transactions were modified.")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Costume Store Production Neon Database Initialization & Catalogue Importer")
    parser.add_argument(
        '--target-db',
        help="(Optional fallback) Target database connection URL. Note: Setting TARGET_DATABASE_URL environment variable is preferred."
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help="Perform non-destructive dry-run inspection of target database."
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help="Mandatory confirmation flag to execute database schema creation and catalogue import."
    )
    args = parser.parse_args()

    if args.check:
        check_database_status(args.target_db)
        return

    if not args.confirm:
        print("[SAFETY ABORT] Execution cancelled.")
        print("To inspect target database schema without writing:")
        print("  python scripts/import_catalogue.py --check")
        print("To execute schema creation and catalogue import, set TARGET_DATABASE_URL and provide --confirm:")
        print("  export TARGET_DATABASE_URL='postgresql://user:pass@ep-xyz-pooler.region.aws.neon.tech/neondb?sslmode=require'")
        print("  python scripts/import_catalogue.py --confirm")
        sys.exit(1)

    if args.target_db:
        print("[SECURITY NOTICE] Target DB passed via CLI argument. For production safety, prefer using TARGET_DATABASE_URL environment variable.")

    run_catalogue_import(args.target_db)


if __name__ == '__main__':
    main()
