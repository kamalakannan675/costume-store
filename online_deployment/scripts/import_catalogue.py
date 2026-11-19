"""
COSTUME STORE — Catalogue Migration & Import Utility
Explicitly invoked standalone utility to import the approved catalogue into a
newly provisioned target database (Neon PostgreSQL in production, or SQLite in development).

Includes:
  - 32 Categories (hierarchy preserved)
  - 26 Approved Indian traditional products
  - 97 Product variants (sizes, colours, stock counts)
  - 26 Product image records
  - 4 Discount coupons
  - 10 Store settings

Explicitly EXCLUDES:
  - Administrator and customer accounts
  - Historical orders and order items
  - Payment transactions
  - Customer addresses, reviews, wishlists, and OTP tokens

Recommended Usage (Protected Environment Variable):
  # Linux / macOS / Bash:
  export TARGET_DATABASE_URL="postgresql://user:pass@ep-name-pooler.region.aws.neon.tech/neondb?sslmode=require"
  python scripts/import_catalogue.py --confirm
  unset TARGET_DATABASE_URL

  # Windows PowerShell:
  $env:TARGET_DATABASE_URL="postgresql://user:pass@ep-name-pooler.region.aws.neon.tech/neondb?sslmode=require"
  python scripts/import_catalogue.py --confirm
  Remove-Item Env:\TARGET_DATABASE_URL
"""

import os
import sys
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def run_catalogue_import(target_db_url: str = None):
    """Imports the approved 26-product catalogue idempotently into the target database."""
    effective_url = target_db_url or os.environ.get('TARGET_DATABASE_URL') or os.environ.get('DATABASE_URL')
    if effective_url:
        os.environ['DATABASE_URL'] = effective_url

    from config import normalize_database_url
    from app import app
    from models import db, Category, Product, ProductVariant, ProductImage, Coupon, StoreSetting
    from scripts.seed_database import seed_database

    if effective_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_url(effective_url)

    target_uri = app.config['SQLALCHEMY_DATABASE_URI']
    safe_display_url = target_uri
    if '@' in safe_display_url and '://' in safe_display_url:
        prefix, rest = safe_display_url.split('://', 1)
        creds, host_part = rest.split('@', 1)
        user = creds.split(':')[0]
        safe_display_url = f"{prefix}://{user}:****@{host_part}"

    print("=" * 70)
    print("COSTUME STORE — CATALOGUE IMPORT & MIGRATION")
    print("=" * 70)
    print(f"Target Database : {safe_display_url}")
    print("=" * 70)

    with app.app_context():
        print("\n[Step 1/2] Ensuring database schema tables exist...")
        db.create_all()

        print("[Step 2/2] Seeding approved 26-product Indian catalogue...")
        seed_database()

        db_prod_count = Product.query.filter_by(is_active=True).count()
        db_var_count = ProductVariant.query.filter_by(is_active=True).count()
        db_img_count = ProductImage.query.count()
        db_cat_count = Category.query.count()
        db_coup_count = Coupon.query.count()
        db_set_count = StoreSetting.query.count()

        print(f"  -> Total Categories:      {db_cat_count} (Expected: 32)")
        print(f"  -> Total Active Products: {db_prod_count} (Expected: 26)")
        print(f"  -> Total Active Variants: {db_var_count} (Expected: 97)")
        print(f"  -> Total Images:          {db_img_count} (Expected: 26)")
        print(f"  -> Total Coupons:         {db_coup_count} (Expected: 4)")
        print(f"  -> Total Store Settings:  {db_set_count} (Expected: 10)")

        print("\n" + "=" * 70)
        print("CATALOGUE IMPORT COMPLETED SUCCESSFULLY!")
        print("Personal accounts, orders, reviews, and transactions were NOT touched.")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Costume Store Catalogue Import Utility")
    parser.add_argument(
        '--target-db',
        help="(Optional fallback) Target database connection URL. Note: Setting TARGET_DATABASE_URL environment variable is preferred to keep credentials out of shell history."
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help="Mandatory confirmation flag to execute database write operations."
    )
    args = parser.parse_args()

    if not args.confirm:
        print("[SAFETY ABORT] Execution cancelled.")
        print("To execute catalogue import, provide the --confirm flag and set TARGET_DATABASE_URL:")
        print("  export TARGET_DATABASE_URL='postgresql://user:pass@ep-xyz-pooler.region.aws.neon.tech/neondb?sslmode=require'")
        print("  python scripts/import_catalogue.py --confirm")
        sys.exit(1)

    if args.target_db:
        print("[SECURITY NOTICE] Target DB passed via CLI argument. For production safety, prefer using the TARGET_DATABASE_URL environment variable to avoid storing credentials in shell history.")

    run_catalogue_import(args.target_db)


if __name__ == '__main__':
    main()
