"""
COSTUME STORE — Online Copy Local Development Server
Usage:
    python run.py

Starts the local development server for the online deployment codebase on http://127.0.0.1:5000
using its own independent SQLite instance in online_deployment/instance/.
"""

import os
import sys

# Ensure local development configuration
os.environ.setdefault('FLASK_ENV', 'development')

from app import app
from models import db, Product
from scripts.init_db import init_db


def ensure_database():
    """Verify local database exists and is properly seeded with approved products."""
    with app.app_context():
        try:
            prod_count = Product.query.filter_by(is_active=True).count()
            if prod_count < 26:
                print(f"[INFO] Initializing online copy local database (current count: {prod_count})...")
                init_db()
        except Exception:
            print("[INFO] Database uninitialized. Running initial schema setup and catalogue seeding...")
            init_db()


def main():
    ensure_database()

    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")

    print("\n" + "=" * 68)
    print("  COSTUME STORE — ONLINE DEPLOYMENT (LOCAL DEV SERVER)")
    print("=" * 68)
    print(f"  * Storefront URL:      http://{host}:{port}/")
    print(f"  * Product Catalogue:   http://{host}:{port}/shop")
    print(f"  * Admin Panel Login:   http://{host}:{port}/admin/login")
    print(f"  * Health Check:        http://{host}:{port}/health")
    print(f"  * Active Catalogue:    26 Indian Traditional Attire Products")
    print(f"  * Database:            online_deployment/instance/costume_store.db")
    print("=" * 68 + "\n")

    app.run(host=host, port=port, debug=True)


if __name__ == '__main__':
    main()
