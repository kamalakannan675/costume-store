"""
COSTUME STORE — Database Initialization & Verification Script
Initializes a clean, fresh local SQLite database, creates schema tables,
and seeds the approved 26 Indian traditional clothing products.

Features:
- Protected --reset requiring explicit target display and user confirmation.
- Refuses to reset remote, production, or non-project databases.
- Distinguishes Administrator accounts from Customer accounts.
- Preserves administrator accounts during non-destructive initialization.
"""

import os
import sys

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app
from models import (
    db, Category, Product, ProductImage, ProductVariant,
    User, Order, OrderItem, ProductReview, PaymentTransaction,
    Coupon, StoreSetting, ContactMessage, InventoryRestockLog
)
from scripts.seed_database import seed_database


def validate_database_target_for_reset(db_uri, project_dir=None, allow_testing_memory=False):
    """
    Validates that a target database URI is a genuine local SQLite file strictly
    contained within the project directory. Rejects remote databases, non-SQLite
    databases, outside paths, prefix-sibling paths, and symlinks pointing outside.
    Returns the canonical resolved absolute path of the target database file.
    """
    if not db_uri or not isinstance(db_uri, str):
        raise ValueError("[SECURITY REFUSAL] Database URI must be a non-empty string.")

    # 1. Reject non-SQLite or remote database URLs
    clean_uri = db_uri.strip()
    if not clean_uri.startswith('sqlite:///'):
        raise RuntimeError(
            f"[SECURITY REFUSAL] Refusing to reset non-SQLite or remote database URI: '{clean_uri}'."
        )

    # 2. Reject in-memory or pseudo database paths unless explicitly allowed in test harness
    raw_path = clean_uri[len('sqlite:///'):].strip()
    if raw_path == ':memory:' and allow_testing_memory:
        return ':memory:'
    if not raw_path or raw_path == ':memory:' or raw_path.startswith('?'):
        raise RuntimeError(
            "[SECURITY REFUSAL] Refusing to reset ephemeral or in-memory SQLite database."
        )

    base_proj = os.path.realpath(os.path.abspath(project_dir or BASE_DIR))

    # Resolve target file path (resolves relative paths, . / .., and symlinks)
    if not os.path.isabs(raw_path):
        candidate_path = os.path.join(base_proj, raw_path)
    else:
        candidate_path = raw_path

    resolved_target = os.path.realpath(os.path.abspath(candidate_path))

    # 3. Verify target is strictly within the project directory using os.path.commonpath
    try:
        common = os.path.commonpath([base_proj, resolved_target])
    except ValueError:
        # Different drives on Windows (e.g. C: vs D:)
        raise RuntimeError(
            f"[SECURITY REFUSAL] Target database '{resolved_target}' resides on a different drive than project '{base_proj}'."
        )

    # Must be genuinely contained inside project_dir and not equal to project_dir itself
    if common != base_proj or resolved_target == base_proj:
        raise RuntimeError(
            f"[SECURITY REFUSAL] Target database '{resolved_target}' is outside project directory '{base_proj}'."
        )

    # Extra defense against prefix-sibling directories
    rel_path = os.path.relpath(resolved_target, base_proj)
    if rel_path.startswith('..') or os.path.isabs(rel_path):
        raise RuntimeError(
            f"[SECURITY REFUSAL] Path traversal or sibling directory detected: '{resolved_target}'."
        )

    return resolved_target


def init_db(reset=False, confirmed=False):
    """
    Initialize schema and seed catalogue into instance/costume_store.db.
    If reset=True, validates database target, displays path and warning,
    requires confirmation, and recreates tables.
    """
    with app.app_context():
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        
        if reset:
            # Strictly validate the database target before performing any destructive actions
            raw_path = validate_database_target_for_reset(
                db_uri,
                BASE_DIR,
                allow_testing_memory=bool(app.config.get('TESTING'))
            )

            # Display target and clear warning
            print("\n" + "!" * 68)
            print("  [CRITICAL WARNING] DESTRUCTIVE DATABASE RESET REQUESTED")
            print("!" * 68)
            print(f"  Target Database File: {raw_path}")
            print("  ALL existing tables, catalogue items, user accounts,")
            print("  orders, and settings will be PERMANENTLY DESTROYED.")
            print("!" * 68 + "\n")

            # Require explicit confirmation before dropping tables
            if not confirmed:
                try:
                    response = input("Type 'CONFIRM' to permanently drop all tables and reset: ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\n[CANCELLED] Database reset cancelled by user.")
                    sys.exit(0)

                if response != "CONFIRM":
                    print(f"[CANCELLED] Input '{response}' did not match 'CONFIRM'. Reset aborted.")
                    sys.exit(0)

            print(f"[INFO] Confirmation verified. Dropping all tables in {raw_path}...")
            db.drop_all()
        else:
            if db_uri.startswith('sqlite:///'):
                raw_path = db_uri[len('sqlite:///'):]
                if not os.path.isabs(raw_path):
                    raw_path = os.path.abspath(os.path.join(BASE_DIR, raw_path))
                raw_path = os.path.normpath(raw_path)
            else:
                raw_path = db_uri

        print("[INFO] Creating database schema tables...")
        db.create_all()

        print("[INFO] Seeding approved 26-product Indian traditional attire catalogue...")
        active_count = seed_database()

        # Verification metrics distinguishing Administrator and Customer accounts
        admin_count = User.query.filter_by(is_admin=True).count()
        customer_count = User.query.filter_by(is_admin=False).count()
        order_count = Order.query.count()
        order_item_count = OrderItem.query.count()
        payment_count = PaymentTransaction.query.count()
        review_count = ProductReview.query.count()
        active_prod_count = Product.query.filter_by(is_active=True).count()
        total_prod_count = Product.query.count()
        storefront_cat_count = Category.query.filter_by(parent_id=None, is_visible_on_storefront=True).count()
        dormant_cat_count = Category.query.filter_by(parent_id=None, is_visible_on_storefront=False).count()
        total_cat_count = Category.query.count()
        subcat_count = Category.query.filter(Category.parent_id.isnot(None)).count()
        variant_count = ProductVariant.query.count()

        print("\n" + "=" * 65)
        print("DATABASE INITIALIZATION & VERIFICATION SUMMARY")
        print("=" * 65)
        print(f"Database File:          {raw_path}")
        print(f"Storefront Categories:  {storefront_cat_count} (Expected: 4)")
        print(f"Dormant Categories:     {dormant_cat_count} (Admin only: 4)")
        print(f"Total Categories:       {total_cat_count}")
        print(f"Subcategories:          {subcat_count}")
        print(f"Active Products:        {active_prod_count} (Expected: 26)")
        print(f"Total Products:         {total_prod_count} (Expected: 26)")
        print(f"Product Variants:       {variant_count} (Expected: 97)")
        print(f"Administrator Accounts: {admin_count} (Expected: 1 if provisioned, 0 otherwise)")
        print(f"Customer Accounts:      {customer_count} (Expected: 0)")
        print(f"Historical Orders:      {order_count} (Expected: 0)")
        print(f"Order Items:            {order_item_count} (Expected: 0)")
        print(f"Customer Reviews:       {review_count} (Expected: 0)")
        print(f"Payment Records:        {payment_count} (Expected: 0)")
        print("=" * 65)

        # Invariant validations
        assert storefront_cat_count == 4, f"Expected 4 storefront categories, got {storefront_cat_count}"
        assert active_prod_count == 26, f"Expected 26 active products, got {active_prod_count}"
        assert customer_count == 0, f"Expected 0 customer records, got {customer_count}"
        assert order_count == 0, f"Expected 0 historical orders, got {order_count}"
        assert order_item_count == 0, f"Expected 0 order items, got {order_item_count}"
        assert review_count == 0, f"Expected 0 customer reviews, got {review_count}"
        assert payment_count == 0, f"Expected 0 payment records, got {payment_count}"

        print("[SUCCESS] Database verification passed cleanly!\n")
        return True


if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    confirmed_flag = "--yes" in sys.argv or "-y" in sys.argv or "--confirm" in sys.argv
    init_db(reset=reset_flag, confirmed=confirmed_flag)
