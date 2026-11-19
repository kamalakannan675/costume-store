"""
COSTUME STORE — Online Deployment Comprehensive Test Suite
Verifies all 22 core deployment requirements independently without touching offline files or databases.
"""

import os
import sys
import unittest
import tempfile
import json
import io
import hmac
import hashlib
from datetime import datetime, timedelta

# Ensure online_deployment root is at the front of sys.path
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ONLINE_ROOT = os.path.dirname(TEST_DIR)
OFFLINE_ROOT = os.path.dirname(ONLINE_ROOT)

if ONLINE_ROOT in sys.path:
    sys.path.remove(ONLINE_ROOT)
sys.path.insert(0, ONLINE_ROOT)

# Set testing environment before importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['FLASK_SECRET_KEY'] = 'online-deployment-testing-secret-key-32chars!'
os.environ['OTP_SECRET_KEY'] = 'online-deployment-testing-otp-secret-key-32chars!'
os.environ['ADMIN_EMAIL'] = 'onlineadmin@example.com'
os.environ['ADMIN_NAME'] = 'Online Super Admin'
os.environ['ADMIN_PASSWORD'] = 'OnlineAdmin@2026'

from config import Config, ProductionConfig, DevelopmentConfig, TestingConfig, normalize_database_url
from storage_service import storage_service
from models import (
    db, User, Address, Category, Product, ProductVariant, ProductImage,
    Coupon, Order, OrderItem, PaymentTransaction, StoreSetting
)
from app import app, sync_admin_from_env
from sales_service import get_dashboard_analytics, get_sales_chart_data, generate_sales_csv, generate_sales_excel, generate_sales_pdf


class OnlineDeploymentTestCase(unittest.TestCase):
    """Test suite verifying online deployment codebase independence and security."""

    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.temp_db_fd, cls.temp_db_path = tempfile.mkstemp(suffix='.db', prefix='test_online_')
        os.close(cls.temp_db_fd)
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{cls.temp_db_path.replace(os.sep, '/')}"
        
        cls.temp_upload_dir = tempfile.mkdtemp(prefix='test_online_uploads_')
        app.config['UPLOAD_FOLDER'] = cls.temp_upload_dir
        storage_service.init_app(app)

        with app.app_context():
            db.create_all()
            cls._seed_minimal_data()

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(cls.temp_db_path):
            try:
                os.remove(cls.temp_db_path)
            except OSError:
                pass
        if os.path.exists(cls.temp_upload_dir):
            import shutil
            shutil.rmtree(cls.temp_upload_dir, ignore_errors=True)

    @classmethod
    def _seed_minimal_data(cls):
        # Category
        cat = Category(name="Women Ethnic", slug="women-ethnic", is_active=True, is_visible_on_storefront=True)
        db.session.add(cat)
        db.session.flush()

        # Product
        p = Product(
            name="Banarasi Silk Saree",
            slug="banarasi-silk-saree",
            description="Traditional Banarasi silk saree.",
            details="Care: Dry clean only.",
            category_id=cat.id,
            base_price=3500.0,
            discount_price=2999.0,
            sku="BAN-SAR-001",
            is_active=True
        )
        db.session.add(p)
        db.session.flush()

        # Image
        img = ProductImage(product_id=p.id, image_url="/static/images/products/women/banarasi-saree-01.jpg", is_primary=True)
        db.session.add(img)

        # Variant
        v = ProductVariant(
            product_id=p.id,
            size="Free Size",
            colour="Crimson Red",
            colour_code="#990000",
            sku="BAN-SAR-001-FS-RED",
            stock_quantity=15,
            is_active=True
        )
        db.session.add(v)

        # Coupon
        coupon = Coupon(code="FESTIVE10", discount_type="percentage", discount_value=10.0, min_purchase=1000.0, is_active=True)
        db.session.add(coupon)

        # Store Settings
        StoreSetting.set('cod_enabled', 'true')
        StoreSetting.set('delivery_charge', '99.0')
        StoreSetting.set('free_delivery_threshold', '1499.0')

        db.session.commit()

    def setUp(self):
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    # --------------------------------------------------------------------------
    # 1. INDEPENDENT IMPORTS & APP BOOT
    # --------------------------------------------------------------------------
    def test_01_imports_independently_and_starts(self):
        """Verify online application imports and boots with healthy config."""
        self.assertIsNotNone(app)
        self.assertEqual(app.name, "app")
        self.assertTrue(hasattr(app, 'config'))

    # --------------------------------------------------------------------------
    # 2. PRODUCTION CONFIGURATION VALIDATION & FAILURES
    # --------------------------------------------------------------------------
    def test_02_production_config_validation_and_failures(self):
        """Verify production mode rejects missing/weak secrets and non-Postgres DB URLs."""
        # Missing secret
        with self.assertRaises(RuntimeError) as cm:
            ProductionConfig.validate(secret_key="", database_url="postgresql://u:p@localhost/db")
        self.assertIn("FLASK_SECRET_KEY environment variable is missing", str(cm.exception))

        # Too short secret
        with self.assertRaises(RuntimeError) as cm:
            ProductionConfig.validate(secret_key="shortkey", database_url="postgresql://u:p@localhost/db")
        self.assertIn("too short", str(cm.exception))

        # Predictable secret
        with self.assertRaises(RuntimeError) as cm:
            ProductionConfig.validate(secret_key="my-default-secret-key-12345678901234", database_url="postgresql://u:p@localhost/db")
        self.assertIn("insecure default/placeholder words", str(cm.exception))

        # Missing DATABASE_URL
        with self.assertRaises(RuntimeError) as cm:
            ProductionConfig.validate(
                secret_key="c8f1e29d4a8b7c6e5f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e",
                database_url=""
            )
        self.assertIn("DATABASE_URL is missing", str(cm.exception))

        # SQLite prohibited in production
        with self.assertRaises(RuntimeError) as cm:
            ProductionConfig.validate(
                secret_key="c8f1e29d4a8b7c6e5f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e",
                database_url="sqlite:///instance/costume_store.db"
            )
        self.assertIn("Production mode strictly prohibits SQLite", str(cm.exception))

    # --------------------------------------------------------------------------
    # 3. DATABASE URL NORMALIZATION & POSTGRESQL READINESS
    # --------------------------------------------------------------------------
    def test_03_database_url_normalization(self):
        """Verify postgres:// is correctly normalized to postgresql+psycopg2:// and sslmode=require is enforced."""
        raw = "postgres://usr:pwd@db-host.com:5432/costumedb"
        normalized = normalize_database_url(raw)
        self.assertEqual(normalized, "postgresql+psycopg2://usr:pwd@db-host.com:5432/costumedb?sslmode=require")

    # --------------------------------------------------------------------------
    # 4. ZERO REFERENCE TO OFFLINE DATABASE
    # --------------------------------------------------------------------------
    def test_04_no_reference_to_offline_database(self):
        """Verify the online app never references the offline database."""
        offline_db_path = os.path.join(OFFLINE_ROOT, "instance", "costume_store.db").replace(os.sep, "/")
        current_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        self.assertNotIn(offline_db_path, current_uri)

    # --------------------------------------------------------------------------
    # 5. HEALTH CHECK ENDPOINT
    # --------------------------------------------------------------------------
    def test_05_health_check_endpoint(self):
        """Verify /health returns 200 OK and database connected."""
        res = self.client.get('/health')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data.get('status'), 'healthy')
        self.assertEqual(data.get('database'), 'connected')

    # --------------------------------------------------------------------------
    # 6. STORAGE SERVICE ABSTRACTION
    # --------------------------------------------------------------------------
    def test_06_storage_service_validation_and_security(self):
        """Verify image validation, mime checking, path traversal protection, and persistence."""
        # Invalid extension
        dummy_txt = io.BytesIO(b"malicious script")
        dummy_txt.filename = "script.php"
        dummy_txt.content_type = "text/plain"
        valid, msg = storage_service.validate_image_file(dummy_txt)
        self.assertFalse(valid)
        self.assertIn("not supported", msg)

        # Valid image
        dummy_img = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...")
        dummy_img.filename = "festive_saree.png"
        dummy_img.content_type = "image/png"
        valid, msg = storage_service.validate_image_file(dummy_img)
        self.assertTrue(valid)

        # Save image via storage_service
        saved_url = storage_service.save_image(dummy_img, prefix="test")
        self.assertTrue(saved_url.startswith("/static/uploads/products/"))
        self.assertTrue(saved_url.endswith(".png"))

        # Verify physical file exists in temp upload folder
        fname = os.path.basename(saved_url)
        self.assertTrue(os.path.exists(os.path.join(self.temp_upload_dir, fname)))

        # Delete image
        deleted = storage_service.delete_image(saved_url)
        self.assertTrue(deleted)
        self.assertFalse(os.path.exists(os.path.join(self.temp_upload_dir, fname)))

        # Protection: Bundled static images should NOT be deleted
        static_img_url = "/static/images/products/women/banarasi-saree-01.jpg"
        self.assertFalse(storage_service.delete_image(static_img_url))

    # --------------------------------------------------------------------------
    # 7. INDEPENDENT ADMINISTRATOR PROVISIONING
    # --------------------------------------------------------------------------
    def test_07_independent_admin_provisioning(self):
        """Verify sync_admin_from_env provisions admin into isolated DB with Werkzeug hash."""
        admin = sync_admin_from_env(app)
        self.assertIsNotNone(admin)
        self.assertEqual(admin.email, "onlineadmin@example.com")
        self.assertTrue(admin.is_admin)
        self.assertTrue(admin.check_password("OnlineAdmin@2026"))
        self.assertFalse(admin.check_password("WrongPassword123"))

    # --------------------------------------------------------------------------
    # 8. CUSTOMER REGISTRATION & VALIDATION
    # --------------------------------------------------------------------------
    def test_08_customer_registration_and_validation(self):
        """Verify customer registration with strict validation."""
        # Keyboard mash rejection
        res = self.client.post('/register', data={
            'name': 'asdfasdfasdf',
            'email': 'validuser@example.com',
            'password': 'SecurePassword@123',
            'confirm_password': 'SecurePassword@123',
            'phone': '9876543210',
            'street_address': '12 Gandhi Road',
            'state': 'Tamil Nadu',
            'city': 'Chennai',
            'pincode': '600001'
        }, follow_redirects=True)
        self.assertIn(b'keyboard patterns', res.data.lower())

        # Valid registration
        res2 = self.client.post('/register', data={
            'name': 'Ravi Kumar',
            'email': 'ravikumar@example.com',
            'password': 'SecurePassword@123',
            'confirm_password': 'SecurePassword@123',
            'phone': '9876543210',
            'street_address': '12 Gandhi Road',
            'state': 'Tamil Nadu',
            'city': 'Chennai',
            'pincode': '600001'
        }, follow_redirects=True)
        self.assertIn(b'account created successfully', res2.data.lower())

        user = User.query.filter_by(email='ravikumar@example.com').first()
        self.assertIsNotNone(user)
        self.assertFalse(user.is_admin)

    # --------------------------------------------------------------------------
    # 9. LOGIN AND LOGOUT
    # --------------------------------------------------------------------------
    def test_09_customer_login_and_logout(self):
        """Verify customer login session creation and logout destruction."""
        res = self.client.post('/login', data={
            'email': 'ravikumar@example.com',
            'password': 'SecurePassword@123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertIn('user_id', sess)

        # Logout
        res_logout = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(res_logout.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)

    # --------------------------------------------------------------------------
    # 10. ADMIN AUTHORIZATION ENFORCEMENT
    # --------------------------------------------------------------------------
    def test_10_admin_authorization_enforcement(self):
        """Verify non-admin customer cannot access /admin/dashboard."""
        # Unauthenticated
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 302)
        self.assertIn('login', res.headers.get('Location', ''))

        # Logged in as normal customer
        cust = User.query.filter_by(email='ravikumar@example.com').first()
        with self.client.session_transaction() as sess:
            sess['user_id'] = cust.id

        res2 = self.client.get('/admin/dashboard', follow_redirects=True)
        self.assertIn(b'administrator access required', res2.data.lower())

    # --------------------------------------------------------------------------
    # 11. CATALOGUE BROWSING ROUTES
    # --------------------------------------------------------------------------
    def test_11_product_catalogue_routes(self):
        """Verify storefront index, shop, and product detail routes respond cleanly."""
        res_home = self.client.get('/')
        self.assertEqual(res_home.status_code, 200)

        res_shop = self.client.get('/shop')
        self.assertEqual(res_shop.status_code, 200)

        res_prod = self.client.get('/product/banarasi-silk-saree', follow_redirects=True)
        self.assertEqual(res_prod.status_code, 200)
        self.assertIn(b'Banarasi Silk Saree', res_prod.data)

    # --------------------------------------------------------------------------
    # 12. CART WORKFLOW
    # --------------------------------------------------------------------------
    def test_12_cart_workflow(self):
        """Verify adding, updating, and removing items from the customer cart."""
        p = Product.query.filter_by(slug="banarasi-silk-saree").first()
        v = ProductVariant.query.filter_by(sku="BAN-SAR-001-FS-RED").first()
        cust = User.query.filter_by(email='ravikumar@example.com').first()

        # Login customer first
        with self.client.session_transaction() as sess:
            sess['user_id'] = cust.id

        res = self.client.post('/cart/add', data={
            'product_id': p.id,
            'variant_id': v.id,
            'quantity': 2
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertIn('costume_cart', sess)
            cart_key = str(v.id)
            self.assertIn(cart_key, sess['costume_cart'])
            self.assertEqual(sess['costume_cart'][cart_key]['quantity'], 2)

    # --------------------------------------------------------------------------
    # 13. CHECKOUT & ORDER CREATION
    # --------------------------------------------------------------------------
    def test_13_checkout_and_order_creation(self):
        """Verify order placement snapshots address and decrements stock."""
        p = Product.query.filter_by(slug="banarasi-silk-saree").first()
        v = ProductVariant.query.filter_by(sku="BAN-SAR-001-FS-RED").first()
        initial_stock = v.stock_quantity

        # Login customer and seed cart
        cust = User.query.filter_by(email='ravikumar@example.com').first()
        with self.client.session_transaction() as sess:
            sess['user_id'] = cust.id
            sess['costume_cart'] = {
                str(v.id): {
                    'variant_id': v.id,
                    'quantity': 1
                }
            }

        res = self.client.post('/checkout/process', data={
            'full_name': 'Ravi Kumar',
            'email': 'ravikumar@example.com',
            'phone': '9876543210',
            'shipping_address': '12 Gandhi Road',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pincode': '600001',
            'payment_method': 'cod'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Stock decremented
        db.session.refresh(v)
        self.assertEqual(v.stock_quantity, initial_stock - 1)

        # Order created
        order = Order.query.filter_by(email='ravikumar@example.com').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.payment_method, 'cod')

    # --------------------------------------------------------------------------
    # 14. RAZORPAY VERIFICATION
    # --------------------------------------------------------------------------
    def test_14_razorpay_signature_verification(self):
        """Verify Razorpay payment verification enforces HMAC-SHA256 signature checks."""
        app.config['RAZORPAY_KEY_ID'] = 'rzp_test_mock_12345'
        app.config['RAZORPAY_KEY_SECRET'] = 'test_secret_key_12345'
        order_id = "order_fake123456"
        payment_id = "pay_fake987654"

        # Generate genuine signature
        msg = f"{order_id}|{payment_id}".encode('utf-8')
        valid_sig = hmac.new('test_secret_key_12345'.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        # Create payment record
        cart_payload = {
            'order_number': 'CST-TEST-RZP-001',
            'customer_id': None,
            'full_name': 'Ravi Kumar',
            'email': 'ravikumar@example.com',
            'phone': '9876543210',
            'shipping_address': '12 Gandhi Road',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pincode': '600001',
            'subtotal': 2999.0,
            'discount_amount': 0.0,
            'coupon_code': None,
            'delivery_fee': 0.0,
            'total_amount': 2999.0,
            'items': []
        }
        pt = PaymentTransaction(
            gateway_order_id=order_id,
            amount_paise=299900,
            cart_json=json.dumps(cart_payload),
            status='created'
        )
        db.session.add(pt)
        db.session.commit()

        # Invalid signature must be rejected
        res_invalid = self.client.post('/payment/verify', data={
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': 'invalid_signature_tampered'
        })
        self.assertIn(b'verification failed', res_invalid.data.lower())

        # Valid signature succeeds
        res_valid = self.client.post('/payment/verify', data={
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': valid_sig
        })
        self.assertEqual(res_valid.status_code, 200)

    # --------------------------------------------------------------------------
    # 15. SALES DASHBOARD & EXPORTS
    # --------------------------------------------------------------------------
    def test_15_sales_dashboard_and_export_reports(self):
        """Verify sales analytics calculation and CSV/Excel/PDF exports."""
        from sales_service import get_sales_report_data
        analytics = get_dashboard_analytics()
        self.assertIn('kpis', analytics)
        self.assertIn('total_revenue', analytics['kpis'])
        self.assertIn('inventory', analytics)

        report_data = get_sales_report_data('all')
        self.assertIn('summary', report_data)

        # CSV export
        csv_data = generate_sales_csv(report_data)
        self.assertTrue(len(csv_data) > 0)
        self.assertIn(b"COSTUME STORE", csv_data)

        # Excel export
        excel_io = generate_sales_excel(report_data)
        excel_bytes = excel_io.getvalue() if hasattr(excel_io, 'getvalue') else excel_io
        self.assertTrue(len(excel_bytes) > 0)

        # PDF export
        pdf_io = generate_sales_pdf(report_data)
        pdf_bytes = pdf_io.getvalue() if hasattr(pdf_io, 'getvalue') else pdf_io
        self.assertTrue(len(pdf_bytes) > 0)

    # --------------------------------------------------------------------------
    # 16. CATALOGUE IMPORT UTILITY SAFETY & EXECUTION
    # --------------------------------------------------------------------------
    def test_16_catalogue_import_utility_safety_and_execution(self):
        """Verify scripts/import_catalogue.py aborts without --confirm and imports cleanly with --confirm."""
        import subprocess

        script_path = os.path.join(ONLINE_ROOT, "scripts", "import_catalogue.py")

        # 1. Without --confirm: must abort safely with exit code 1
        res_abort = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_abort.returncode, 1)
        self.assertIn("SAFETY ABORT", res_abort.stdout)

        # 2. With --confirm against an isolated temporary database
        temp_import_fd, temp_import_db = tempfile.mkstemp(suffix='.db', prefix='test_import_')
        os.close(temp_import_fd)
        try:
            target_uri = f"sqlite:///{temp_import_db.replace(os.sep, '/')}"
            res_exec = subprocess.run(
                [sys.executable, script_path, "--target-db", target_uri, "--confirm"],
                capture_output=True,
                text=True
            )
            self.assertEqual(res_exec.returncode, 0)
            self.assertIn("CATALOGUE IMPORT COMPLETED SUCCESSFULLY", res_exec.stdout)
            self.assertIn("Total Active Products: 26", res_exec.stdout)
            self.assertIn("Total Active Variants: 97", res_exec.stdout)
            self.assertIn("Total Images:          26", res_exec.stdout)
        finally:
            if os.path.exists(temp_import_db):
                try:
                    os.remove(temp_import_db)
                except OSError:
                    pass

    # --------------------------------------------------------------------------
    # 17. VERCEL NATIVE FLASK ENTRYPOINT & FRAMEWORK DETECTION
    # --------------------------------------------------------------------------
    def test_17_vercel_native_flask_entrypoint(self):
        """Verify app.py root entrypoint exposes WSGI app and routes properly without legacy api/index.py."""
        entrypoint_path = os.path.join(ONLINE_ROOT, "app.py")
        self.assertTrue(os.path.exists(entrypoint_path), "app.py must exist at project root for native detection")

        from app import app as native_app
        self.assertIsNotNone(native_app, "app.py must export top-level 'app'")
        
        # Test WSGI test_client through native_app
        v_client = native_app.test_client()
        res = v_client.get('/health')
        self.assertEqual(res.status_code, 200)
        json_data = json.loads(res.data)
        self.assertEqual(json_data.get('status'), 'healthy')

    # --------------------------------------------------------------------------
    # 18. NEON POSTGRESQL URL & SSL NORMALIZATION
    # --------------------------------------------------------------------------
    def test_18_neon_postgresql_url_and_ssl(self):
        """Verify Neon PostgreSQL URL handling, sslmode enforcement and serverless pooling."""
        # 1. normalize_database_url postgres: -> postgresql+psycopg2: and sslmode=require
        neon_raw = "postgres://alex:secret123@ep-sweet-glade-a2z.us-east-2.aws.neon.tech/neondb"
        normalized = normalize_database_url(neon_raw)
        self.assertTrue(normalized.startswith("postgresql+psycopg2://"))
        self.assertIn("sslmode=require", normalized)

        # 2. Preserves already present sslmode
        neon_with_ssl = "postgresql+psycopg2://alex:secret123@ep-sweet-glade-a2z.us-east-2.aws.neon.tech/neondb?sslmode=require"
        normalized_ssl = normalize_database_url(neon_with_ssl)
        self.assertEqual(normalized_ssl.count("sslmode=require"), 1)

        # 3. Serverless pool engine options when VERCEL=1
        os.environ['VERCEL'] = '1'
        try:
            import importlib
            import config
            importlib.reload(config)
            engine_opts = config.Config.SQLALCHEMY_ENGINE_OPTIONS
            self.assertTrue(engine_opts.get('pool_pre_ping'), "pool_pre_ping must be True")
            self.assertEqual(engine_opts.get('pool_size'), 2, "pool_size must be 2 for serverless")
            self.assertEqual(engine_opts.get('max_overflow'), 3, "max_overflow must be 3 for serverless")
            self.assertEqual(engine_opts.get('pool_recycle'), 300, "pool_recycle must be 300")
        finally:
            os.environ.pop('VERCEL', None)
            import importlib
            import config
            importlib.reload(config)

    # --------------------------------------------------------------------------
    # 19. NO ACTIVE RENDER FILES & LEGACY ENTRYPOINT REMOVAL
    # --------------------------------------------------------------------------
    def test_19_no_active_render_or_legacy_files(self):
        """Assert no active Render artifacts or legacy api/index.py exist in online_deployment/."""
        render_yaml = os.path.join(ONLINE_ROOT, "render.yaml")
        procfile = os.path.join(ONLINE_ROOT, "Procfile")
        deployment_docs = os.path.join(ONLINE_ROOT, "deployment_docs")
        api_dir = os.path.join(ONLINE_ROOT, "api")

        self.assertFalse(os.path.exists(render_yaml), "render.yaml should be isolated, not in online_deployment/")
        self.assertFalse(os.path.exists(procfile), "Procfile should be isolated, not in online_deployment/")
        self.assertFalse(os.path.exists(deployment_docs), "deployment_docs/ should be isolated, not in online_deployment/")
        self.assertFalse(os.path.exists(api_dir), "legacy api/ directory must be removed for native Flask detection")

    # --------------------------------------------------------------------------
    # 20. STATIC ASSETS & PUBLIC CDN SERVING
    # --------------------------------------------------------------------------
    def test_20_static_assets_serving(self):
        """Verify core static assets, location data and images are reachable via /static/ and /public CDN."""
        # Verify public/ directory exists
        public_dir = os.path.join(ONLINE_ROOT, "public")
        self.assertTrue(os.path.exists(public_dir), "public/ directory must exist for Vercel CDN")

        # CSS
        res_css = self.client.get('/static/css/style.css')
        self.assertEqual(res_css.status_code, 200)

        # Direct CDN route for CSS
        res_cdn_css = self.client.get('/css/style.css')
        self.assertEqual(res_cdn_css.status_code, 200)

        # JS
        res_js = self.client.get('/static/js/main.js')
        self.assertEqual(res_js.status_code, 200)

        # Direct CDN route for JS
        res_cdn_js = self.client.get('/js/main.js')
        self.assertEqual(res_cdn_js.status_code, 200)

        # India Locations JSON
        res_loc = self.client.get('/static/js/india_locations.json')
        self.assertEqual(res_loc.status_code, 200)

        # Placeholder image
        res_ph = self.client.get('/static/images/placeholder-costume.jpg')
        self.assertEqual(res_ph.status_code, 200)

        # Direct CDN route for images
        res_cdn_ph = self.client.get('/images/placeholder-costume.jpg')
        self.assertEqual(res_cdn_ph.status_code, 200)

        # Catalog product image
        res_img = self.client.get('/static/images/products/women/banarasi-saree-01.jpg')
        self.assertEqual(res_img.status_code, 200)

        # Health endpoint
        res_health = self.client.get('/health')
        self.assertEqual(res_health.status_code, 200)
        data = json.loads(res_health.data)
        self.assertEqual(data.get('status'), 'healthy')

    # --------------------------------------------------------------------------
    # 21. VERCEL SERVERLESS RUNTIME READ-ONLY FILESYSTEM RESILIENCE
    # --------------------------------------------------------------------------
    def test_21_vercel_simulated_import_no_instance_mkdir(self):
        """Verify config.py in Vercel mode disables SQLite, avoids mkdir(/var/task/instance), and uses /tmp."""
        import importlib
        import config

        os.environ['VERCEL'] = '1'
        try:
            importlib.reload(config)
            self.assertTrue(config.is_serverless, "config.is_serverless must be True in Vercel environment")
            self.assertEqual(config.DEFAULT_SQLITE_URI, "", "DEFAULT_SQLITE_URI must be empty in serverless to prevent SQLite fallback")
            
            # Temporary directory helper
            tmp = config.get_temp_dir()
            self.assertTrue(tmp.startswith('/tmp') or 'tmp' in tmp, "get_temp_dir() must provide an ephemeral writable path")
        finally:
            os.environ.pop('VERCEL', None)
            importlib.reload(config)

    # --------------------------------------------------------------------------
    # 22. PRODUCTION SAFE FAILURE ON MISSING DATABASE_URL
    # --------------------------------------------------------------------------
    def test_22_production_missing_database_url_fails_safely(self):
        """Verify ProductionConfig.validate() rejects missing DATABASE_URL with a clear diagnostic."""
        from config import ProductionConfig
        with self.assertRaises(RuntimeError) as cm:
            ProductionConfig.validate(
                database_url="",
                secret_key="a" * 32
            )
        self.assertIn("DATABASE_URL is missing in production", str(cm.exception))
        self.assertIn("Neon", str(cm.exception))

    # --------------------------------------------------------------------------
    # 23. LOCAL SQLITE DEVELOPMENT PRESERVED
    # --------------------------------------------------------------------------
    def test_23_local_development_sqlite_preserved(self):
        """Verify local development preserves SQLite default URI and local instance directory."""
        import importlib
        import config

        os.environ.pop('VERCEL', None)
        os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None)
        importlib.reload(config)

        self.assertFalse(config.is_serverless)
        self.assertTrue(config.DEFAULT_SQLITE_URI.startswith("sqlite:///"))
        self.assertIn("instance/costume_store.db", config.DEFAULT_SQLITE_URI.replace('\\', '/'))

    # --------------------------------------------------------------------------
    # 24. SERVERLESS READ-ONLY STORAGE SAFETY
    # --------------------------------------------------------------------------
    def test_24_serverless_storage_read_only_safety(self):
        """Verify storage_service fails safely with diagnostic when S3 is unconfigured in serverless."""
        from storage_service import StorageService, ReadOnlyDisabledStorageBackend
        dummy_app = type('DummyApp', (), {'config': {'STORAGE_BACKEND': 'local', 'UPLOAD_FOLDER': '/var/task/static/uploads'}, 'logger': app.logger})()
        
        os.environ['VERCEL'] = '1'
        try:
            svc = StorageService()
            svc.init_app(dummy_app)
            self.assertIsInstance(svc.backend, ReadOnlyDisabledStorageBackend)

            # Upload attempt raises descriptive RuntimeError without writing to disk
            mock_file = type('MockFile', (), {'filename': 'test.jpg', 'content_type': 'image/jpeg', 'content_length': 100, 'seek': lambda pos: None, 'read': lambda: b'bytes'})()
            with self.assertRaises(RuntimeError) as cm:
                svc.save_image(mock_file)
            self.assertIn("External persistent storage (S3/R2) is not configured", str(cm.exception))
        finally:
            os.environ.pop('VERCEL', None)

    # --------------------------------------------------------------------------
    # 25. HEALTH CHECK SCHEMA & CATALOGUE READINESS
    # --------------------------------------------------------------------------
    def test_25_health_check_distinguishes_schema_readiness(self):
        """Verify /health returns detailed readiness checks, table count, and catalogue status."""
        res = self.client.get('/health')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data.get('status'), 'healthy')
        self.assertEqual(data.get('database'), 'connected')
        checks = data.get('checks', {})
        self.assertTrue(checks.get('schema_initialized'))
        self.assertTrue(checks.get('catalogue_ready'))
        self.assertGreaterEqual(checks.get('table_count', 0), 17)
        self.assertGreaterEqual(checks.get('categories_count', 0), 32)
        self.assertGreaterEqual(checks.get('active_products_count', 0), 26)

    # --------------------------------------------------------------------------
    # 26. MAINTENANCE INIT ENDPOINT SECURITY
    # --------------------------------------------------------------------------
    def test_26_maintenance_init_endpoint_security(self):
        """Verify /api/maintenance/init-database enforces secret authorization."""
        # Unauthenticated request -> 401 Unauthorized
        res_unauth = self.client.post('/api/maintenance/init-database')
        self.assertEqual(res_unauth.status_code, 401)

        # Invalid secret -> 401 Unauthorized
        res_invalid = self.client.post(
            '/api/maintenance/init-database',
            headers={'X-Maintenance-Secret': 'wrong-secret-token'}
        )
        self.assertEqual(res_invalid.status_code, 401)

        # Valid secret -> 200 OK
        valid_secret = app.config['SECRET_KEY']
        res_valid = self.client.post(
            '/api/maintenance/init-database',
            headers={'X-Maintenance-Secret': valid_secret}
        )
        self.assertEqual(res_valid.status_code, 200)
        resp_json = json.loads(res_valid.data)
        self.assertEqual(resp_json.get('status'), 'success')
        self.assertGreaterEqual(resp_json.get('counts', {}).get('categories'), 32)
        self.assertGreaterEqual(resp_json.get('counts', {}).get('active_products'), 26)

    # --------------------------------------------------------------------------
    # 27. CATALOGUE IMPORTER SAFETY REFUSAL ON OFFLINE DATABASE
    # --------------------------------------------------------------------------
    def test_27_import_catalogue_safety_refusal(self):
        """Verify import_catalogue refuses to run against offline SQLite database."""
        from scripts.import_catalogue import validate_target_url_safety
        offline_uri = "sqlite:///D:/Projects/Costume-sales/instance/costume_store.db"
        with self.assertRaises(RuntimeError) as cm:
            validate_target_url_safety(offline_uri)
        self.assertIn("Refusing to run import against offline SQLite database", str(cm.exception))

    # --------------------------------------------------------------------------
    # 28. REPEATED CATALOGUE IMPORT IDEMPOTENCY
    # --------------------------------------------------------------------------
    def test_28_repeated_catalogue_import_idempotency(self):
        """Verify repeated execution of seed_database() preserves exact entity counts."""
        from scripts.seed_database import seed_database
        from models import Category, Product, ProductVariant, Coupon

        cat_count_1 = Category.query.count()
        prod_count_1 = Product.query.count()
        var_count_1 = ProductVariant.query.count()
        coup_count_1 = Coupon.query.count()

        # Re-run seed_database()
        seed_database()

        self.assertEqual(Category.query.count(), cat_count_1)
        self.assertEqual(Product.query.count(), prod_count_1)
        self.assertEqual(ProductVariant.query.count(), var_count_1)
        self.assertEqual(Coupon.query.count(), coup_count_1)


if __name__ == '__main__':
    unittest.main()
