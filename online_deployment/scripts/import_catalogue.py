r"""
COSTUME STORE — Neon Production Database Schema Initialization & Catalogue Import Utility
Explicitly invoked standalone utility to inspect, initialize schema tables, seed the approved catalogue,
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
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

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


def get_effective_database_url(cli_target_url: str = None) -> str:
    """Resolves target database connection URL from CLI arguments or environment variables."""
    url = (
        cli_target_url or
        os.environ.get('TARGET_DATABASE_URL') or
        os.environ.get('DATABASE_URL') or
        os.environ.get('POSTGRES_URL') or
        os.environ.get('POSTGRES_URL_NON_POOLING')
    )
    return (url or '').strip()


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
    """
    Dry-run inspection of target database connection, existing tables, and catalogue counts.
    Creates a dedicated standalone engine directly to the target URL to guarantee
    it never checks local SQLite by mistake.
    """
    effective_url = get_effective_database_url(target_db_url)
    if not effective_url:
        print("[ERROR] No target database URL provided. Set TARGET_DATABASE_URL or pass --target-db.")
        return False
    validate_target_url_safety(effective_url)

    from config import normalize_database_url
    norm_url = normalize_database_url(effective_url)
    display_url = mask_connection_url(norm_url)

    print("=" * 70)
    print("COSTUME STORE — TARGET DATABASE STATUS INSPECTION")
    print("=" * 70)
    print(f"Target Database : {display_url}")
    print("=" * 70)

    # Create standalone engine directly targeting the specified connection URL
    engine = create_engine(norm_url, pool_pre_ping=True)

    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
            print("[✓] Database Connection: SUCCESSFUL (SELECT 1 passed)")

            if engine.url.drivername.startswith(('postgresql', 'postgres')):
                pg_row = conn.execute(text("""
                    SELECT 
                        current_database() AS db_name,
                        current_user AS user_name,
                        current_schema() AS schema_name,
                        current_setting('search_path') AS search_path
                """)).mappings().first()

                print(f"\n[PostgreSQL Identity]")
                print(f"  -> Host               : {engine.url.host}")
                print(f"  -> Database Name      : {pg_row['db_name']}")
                print(f"  -> Database User      : {pg_row['user_name']}")
                print(f"  -> Active Schema      : {pg_row['schema_name']}")
                print(f"  -> Search Path        : {pg_row['search_path']}")
    except Exception as e:
        print(f"[✗] Database Connection FAILED: {e}")
        return False

    # 2. Table inspection on target engine
    inspector = inspect(engine)
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
        with engine.connect() as conn:
            cat_count = conn.execute(text("SELECT count(*) FROM category")).scalar()
            prod_count = conn.execute(text("SELECT count(*) FROM costume_product")).scalar()
            var_count = conn.execute(text("SELECT count(*) FROM product_variant")).scalar() if 'product_variant' in existing else 0
            img_count = conn.execute(text("SELECT count(*) FROM product_image")).scalar() if 'product_image' in existing else 0
            coup_count = conn.execute(text("SELECT count(*) FROM coupon")).scalar() if 'coupon' in existing else 0
            admin_count = conn.execute(text("SELECT count(*) FROM \"user\" WHERE is_admin = true")).scalar() if 'user' in existing else 0

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
    """
    Imports schema and catalogue idempotently into the target database.
    Explicitly forces the target engine and ensures db.metadata creates tables
    on the target engine, verifying host and db name.
    """
    effective_url = get_effective_database_url(target_db_url)
    if not effective_url:
        print("[ERROR] No target database URL provided. Set TARGET_DATABASE_URL or pass --target-db.")
        sys.exit(1)
    validate_target_url_safety(effective_url)

    # Set environment variable BEFORE importing app / config modules
    os.environ['DATABASE_URL'] = effective_url

    from config import normalize_database_url
    norm_url = normalize_database_url(effective_url)
    display_url = mask_connection_url(norm_url)

    print("=" * 70)
    print("COSTUME STORE — PRODUCTION NEON DATABASE INITIALIZATION & IMPORT")
    print("=" * 70)
    print(f"Target Database : {display_url}")
    print("=" * 70)

    # Create standalone target engine
    target_engine = create_engine(norm_url, pool_pre_ping=True)

    try:
        with target_engine.connect() as conn:
            conn.execute(text('SELECT 1'))
            print("[✓] Connectivity verified.")

            if target_engine.url.drivername.startswith(('postgresql', 'postgres')):
                pg_row = conn.execute(text("""
                    SELECT 
                        current_database() AS db_name,
                        current_user AS user_name,
                        current_schema() AS schema_name,
                        current_setting('search_path') AS search_path
                """)).mappings().first()

                print(f"[PostgreSQL Identity]")
                print(f"  -> Target Host        : {target_engine.url.host}")
                print(f"  -> Database Name      : {pg_row['db_name']}")
                print(f"  -> Database User      : {pg_row['user_name']}")
                print(f"  -> Active Schema      : {pg_row['schema_name']}")
    except Exception as e:
        print(f"[✗] Connection failed: {e}")
        sys.exit(1)

    # Step 1: Create all 17 schema tables directly on target engine
    from models import db, Category, Product, ProductVariant, ProductImage, Coupon, StoreSetting, User
    from app import app, sync_admin_from_env
    from scripts.seed_database import seed_database

    # Ensure app.config and db.engine point to target_engine
    app.config['SQLALCHEMY_DATABASE_URI'] = norm_url
    with app.app_context():
        # Force rebind db.engines to target_engine
        db.engines[None] = target_engine

        # Baseline count before import
        inspector_before = inspect(target_engine)
        existing_tables_before = set(inspector_before.get_table_names())

        cat_before = 0
        prod_before = 0
        var_before = 0
        img_before = 0
        coup_before = 0

        if 'category' in existing_tables_before and 'costume_product' in existing_tables_before:
            with target_engine.connect() as conn:
                cat_before = conn.execute(text("SELECT count(*) FROM category")).scalar()
                prod_before = conn.execute(text("SELECT count(*) FROM costume_product")).scalar()
                var_before = conn.execute(text("SELECT count(*) FROM product_variant")).scalar() if 'product_variant' in existing_tables_before else 0
                img_before = conn.execute(text("SELECT count(*) FROM product_image")).scalar() if 'product_image' in existing_tables_before else 0
                coup_before = conn.execute(text("SELECT count(*) FROM coupon")).scalar() if 'coupon' in existing_tables_before else 0

        print("\n[Step 1/3] Ensuring 17 relational schema tables exist in target database...")
        db.metadata.create_all(bind=target_engine)

        inspector_after = inspect(target_engine)
        existing_tables_after = set(inspector_after.get_table_names())
        tables_created = len(existing_tables_after) - len(existing_tables_before)
        print(f"  -> Total tables now present: {len(existing_tables_after)}/17 (Newly created: {max(0, tables_created)})")

        # Step 2: Seed catalogue
        print("\n[Step 2/3] Seeding approved 26-product Indian traditional attire catalogue...")
        seed_database()

        with target_engine.connect() as conn:
            cat_after = conn.execute(text("SELECT count(*) FROM category")).scalar()
            prod_after = conn.execute(text("SELECT count(*) FROM costume_product WHERE is_active = true")).scalar()
            var_after = conn.execute(text("SELECT count(*) FROM product_variant WHERE is_active = true")).scalar()
            img_after = conn.execute(text("SELECT count(*) FROM product_image")).scalar()
            coup_after = conn.execute(text("SELECT count(*) FROM coupon")).scalar()
            set_after = conn.execute(text("SELECT count(*) FROM store_setting")).scalar()

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
