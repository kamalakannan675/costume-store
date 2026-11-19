"""
COSTUME STORE — Vercel Serverless Entrypoint
Exposes the top-level Flask WSGI instance 'app' for Vercel Serverless Functions.
Complies with official Vercel Python runtime guidelines:
https://vercel.com/kb/guide/ship-a-flask-app-on-vercel
"""

import os
import sys

# Ensure online_deployment root is on sys.path so app, models, config are discoverable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app

# Expose WSGI instance for Vercel
app = app
