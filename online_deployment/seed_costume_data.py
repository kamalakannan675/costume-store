"""
COSTUME STORE — Database Seeding Module (Root Wrapper)
Points to scripts/seed_database.py for single source of truth.
"""
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.seed_database import seed_database

if __name__ == '__main__':
    seed_database()
