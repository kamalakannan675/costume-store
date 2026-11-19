from datetime import datetime, timedelta
import os
import io
import json
import hmac
import hashlib
import secrets
import base64
import urllib.request
import urllib.error
import re
import smtplib
from email.message import EmailMessage
from functools import wraps
from urllib.parse import urlparse, urljoin

from flask import (
    Flask, render_template, redirect, url_for,
    session, request, flash, jsonify, abort, send_file, Response
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, desc, func, text, inspect

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from models import (
    db, User, Address, Category, Product, ProductImage, ProductVariant,
    Coupon, Order, OrderItem, Wishlist, ProductReview, StoreSetting,
    PaymentTransaction, OrderStatusLog, OtpToken, ContactMessage, InventoryRestockLog
)
from india_locations import (
    INDIA_STATES_AND_DISTRICTS, is_valid_state, is_valid_district,
    is_valid_pincode, validate_street_address, validate_full_name,
    validate_email_address, normalize_full_name
)
from email_service import (
    send_email,
    is_mail_configured,
    send_order_placed_email,
    send_payment_received_email,
    send_order_status_email,
    send_admin_new_order_alert,
    send_account_deletion_otp,
    send_password_reset_email,
    send_registration_welcome_email
)
from storage_service import storage_service
from sales_service import (
    get_dashboard_analytics,
    get_sales_chart_data,
    get_sales_report_data,
    generate_sales_csv,
    generate_sales_excel,
    generate_sales_pdf
)

# ------------------------------------------------------------------------------
# APPLICATION SETUP
# ------------------------------------------------------------------------------

from config import Config, get_config

app = Flask(__name__)
active_config = get_config()
app.config.from_object(active_config)
ALLOWED_EXTENSIONS = app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'webp', 'gif'})

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db.init_app(app)
storage_service.init_app(app)


# ------------------------------------------------------------------------------
# HELPER FUNCTIONS & DECORATORS
# ------------------------------------------------------------------------------

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def valid_password(password):
    return (
        len(password or '') >= 8 and
        re.search(r'[A-Z]', password) and
        re.search(r'[a-z]', password) and
        re.search(r'\d', password) and
        re.search(r'[^A-Za-z0-9]', password)
    )


def validate_password_strength(password):
    """
    Validates that candidate password satisfies complexity requirements:
    min 8 chars, uppercase, lowercase, digit, special character.
    Raises ValueError with descriptive message if invalid.
    """
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r'[A-Z]', password):
        raise ValueError("Password must contain at least one uppercase letter (A-Z).")
    if not re.search(r'[a-z]', password):
        raise ValueError("Password must contain at least one lowercase letter (a-z).")
    if not re.search(r'\d', password):
        raise ValueError("Password must contain at least one digit (0-9).")
    if not re.search(r'[^A-Za-z0-9]', password):
        raise ValueError("Password must contain at least one special character.")
    return True


def is_safe_url(target):
    """Ensure target URL belongs strictly to the local host and does not redirect off-site."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


_login_failed_attempts = {}


def record_failed_login(ip):
    now = datetime.utcnow()
    attempts = _login_failed_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < timedelta(minutes=15)]
    attempts.append(now)
    _login_failed_attempts[ip] = attempts


def is_login_rate_limited(ip):
    now = datetime.utcnow()
    attempts = _login_failed_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < timedelta(minutes=15)]
    _login_failed_attempts[ip] = attempts
    return len(attempts) >= 10


def reset_failed_login(ip):
    _login_failed_attempts.pop(ip, None)


def create_or_update_admin(email, password, name="Store Administrator", phone=None, address=None, **kwargs):
    """
    Programmatic helper to create or update an administrator account.
    Enforces password complexity requirements.
    """
    if not email or '@' not in email:
        raise ValueError("Valid admin email is required.")
    if not name or len(name.strip()) < 2:
        raise ValueError("Admin name must be at least 2 characters.")
    if not valid_password(password):
        raise ValueError("Password does not satisfy complexity requirements (min 8 chars, uppercase, lowercase, digit, special character).")

    email = email.strip().lower()
    name = name.strip()

    admin = User.query.filter_by(email=email).first()
    if admin:
        admin.name = name
        admin.set_password(password)
        admin.is_admin = True
        if phone:
            admin.phone = phone
        if address:
            admin.address = address
        db.session.commit()
        return admin

    admin = User(
        name=name,
        email=email,
        password=generate_password_hash(password),
        phone=phone,
        address=address,
        is_admin=True,
        is_verified=True
    )
    db.session.add(admin)
    db.session.commit()
    return admin


def sync_admin_from_env(application=None):
    """
    Synchronizes primary administrator account from .env configuration on application startup.
    Reads ADMIN_EMAIL, ADMIN_NAME, and ADMIN_PASSWORD (or deprecated ADMIN_PASSWROD alias).
    Never creates an administrator with a hardcoded default password.
    Never elevates a customer account to administrator.
    Never exposes passwords in logs or error messages.
    """
    admin_email = (os.environ.get('ADMIN_EMAIL') or '').strip().lower()
    admin_name = (os.environ.get('ADMIN_NAME') or '').strip()

    # Check ADMIN_PASSWORD first, then deprecated alias ADMIN_PASSWROD
    raw_password = os.environ.get('ADMIN_PASSWORD')
    if not raw_password:
        alias_password = os.environ.get('ADMIN_PASSWROD')
        if alias_password:
            app.logger.warning("DEPRECATION NOTICE: ADMIN_PASSWROD is deprecated. Please update your environment to use ADMIN_PASSWORD.")
            raw_password = alias_password

    admin_password = (raw_password or '').strip()

    # Find existing verified administrator
    existing_admin = User.query.filter_by(is_admin=True).first()

    # Verify if configuration is complete
    if not admin_email or not admin_name or not admin_password:
        if existing_admin:
            app.logger.info("Admin environment credentials not fully specified in environment. Preserving existing administrator account.")
            return existing_admin
        app.logger.error("Admin account provisioning aborted: ADMIN_EMAIL, ADMIN_NAME, and ADMIN_PASSWORD must all be configured with non-empty values. No hardcoded default credentials will ever be used.")
        return None

    # Validate email syntax
    is_prod = (
        os.environ.get('FLASK_ENV', '').lower() == 'production' or
        bool(os.environ.get('VERCEL')) or
        bool(os.environ.get('RENDER'))
    )
    is_valid_email = False
    if '@' in admin_email:
        local_part, domain_part = admin_email.split('@', 1)
        if local_part and domain_part:
            if not is_prod and domain_part.lower() == 'localhost':
                # Local development environment explicitly permits admin@localhost
                is_valid_email = True
            elif '.' in domain_part and not domain_part.startswith('.') and not domain_part.endswith('.'):
                is_valid_email = True

    if not is_valid_email:
        app.logger.error("Admin synchronization error: Invalid email address format specified in ADMIN_EMAIL.")
        return existing_admin

    # Validate password complexity (5 criteria: min 8, uppercase, lowercase, number, symbol)
    if not valid_password(admin_password):
        app.logger.error("Admin synchronization error: The configured ADMIN_PASSWORD does not satisfy required complexity requirements (minimum 8 characters with uppercase, lowercase, digit, and special character).")
        return existing_admin

    # Check if configured email belongs to an existing customer (is_admin == False)
    customer_conflict = User.query.filter_by(email=admin_email, is_admin=False).first()
    if customer_conflict:
        app.logger.error(f"SECURITY CONFLICT REFUSAL: Configured ADMIN_EMAIL ({admin_email}) belongs to an existing customer account. Refusing to elevate customer account to administrator.")
        return existing_admin

    # If an administrator already exists, update verified admin safely
    if existing_admin:
        changed = False
        # Check if email is being changed and if new email belongs to someone else
        if admin_email != existing_admin.email:
            email_taken = User.query.filter_by(email=admin_email).first()
            if email_taken and email_taken.id != existing_admin.id:
                app.logger.error(f"Cannot update admin email to {admin_email}: Email address is already in use by another account.")
                return existing_admin
            existing_admin.email = admin_email
            changed = True

        if existing_admin.name != admin_name:
            existing_admin.name = admin_name
            changed = True

        if not existing_admin.check_password(admin_password):
            existing_admin.set_password(admin_password)
            changed = True

        if not existing_admin.is_admin:
            existing_admin.is_admin = True
            changed = True

        if not existing_admin.is_verified:
            existing_admin.is_verified = True
            changed = True

        if changed:
            db.session.commit()
            app.logger.info("Admin account synchronized from environment.")
        return existing_admin

    # No administrator exists: provision new single administrator
    new_admin = User(
        name=admin_name,
        email=admin_email,
        password=generate_password_hash(admin_password),
        is_admin=True,
        is_verified=True
    )
    db.session.add(new_admin)
    db.session.commit()
    app.logger.info("Admin account provisioned from environment configuration.")
    return new_admin



def get_otp_secret_key():
    """
    Retrieve dedicated HMAC secret key for OTP verification, failing safely if not configured.
    Strictly requires OTP_SECRET_KEY; never falls back to FLASK_SECRET_KEY to ensure cryptographic key separation.
    """
    key = (app.config.get('OTP_SECRET_KEY') or os.environ.get('OTP_SECRET_KEY') or '').strip()
    if not key:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: OTP_SECRET_KEY is missing or empty. "
            "A dedicated, cryptographically secure OTP_SECRET_KEY is strictly required for OTP operations."
        )
    return key


def generate_otp_verifier(user_id, email, token_type, otp_code):
    """
    Computes a cryptographic HMAC-SHA256 verifier with per-challenge salt and message binding.
    Returns format: f"{salt}${digest}" (length 32 + 1 + 64 = 97 characters).
    """
    key = get_otp_secret_key()
    salt = secrets.token_hex(16)
    message = f"{user_id}:{email}:{token_type}:{salt}:{otp_code}"
    digest = hmac.new(key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{salt}${digest}"


def verify_otp_verifier(stored_hash, user_id, email, token_type, candidate_code):
    """
    Verifies candidate OTP code against stored HMAC verifier using constant-time comparison.
    Requires format: salt$digest where salt is exactly 32 hex characters and digest is exactly 64 hex characters.
    Un-salted or legacy SHA-256 hashes are strictly rejected.
    """
    if not stored_hash or not candidate_code:
        return False

    if '$' not in stored_hash:
        return False

    parts = stored_hash.split('$', 1)
    if len(parts) != 2:
        return False

    salt, expected_digest = parts
    if len(salt) != 32 or len(expected_digest) != 64:
        return False
    if not all(c in '0123456789abcdefABCDEF' for c in salt) or not all(c in '0123456789abcdefABCDEF' for c in expected_digest):
        return False

    key = get_otp_secret_key()
    message = f"{user_id}:{email}:{token_type}:{salt}:{candidate_code}"
    candidate_digest = hmac.new(key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac.compare_digest(candidate_digest.lower(), expected_digest.lower())


def is_category_visible(cat):
    """Recursively verify that a category and all its parent categories are active and visible on storefront."""
    if not cat:
        return False
    curr = cat
    while curr:
        if not curr.is_visible_on_storefront or not curr.is_active:
            return False
        curr = curr.parent
    return True


def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        try:
            uid = int(user_id)
            return db.session.get(User, uid)
        except (ValueError, TypeError):
            return None
    return None


def is_admin_session():
    """Verify administrator authorization based strictly on the authenticated database user's is_admin field."""
    user = get_current_user()
    return bool(user and user.is_admin)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin_session():
            flash('Administrator access required. Please sign in with an admin account.', 'error')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user or user.is_admin:
            flash('Customer login required. Please sign in to proceed.', 'error')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def send_order_email(to_email, subject, body):
    """Send transactional emails if SMTP is configured; fails gracefully without interrupting orders."""
    try:
        html_body = f"<div style='font-family:sans-serif;line-height:1.6;color:#2D2D2D;'>{body.replace(chr(10), '<br>')}</div>"
        return send_email(to_email, subject, html_body, text_content=body)
    except Exception as exc:
        app.logger.warning('Order email could not be sent to %s: %s', to_email, exc)
        return False


def get_cart_data():
    """Calculates real-time cart items, quantities, subtotals, applied discount, and delivery fee."""
    curr_user = get_current_user()
    if not curr_user or curr_user.is_admin:
        return {
            'items': [],
            'subtotal': 0.0,
            'discount_amount': 0.0,
            'delivery_fee': 0.0,
            'total_amount': 0.0,
            'coupon_code': None,
            'coupon_error': None,
            'item_count': 0
        }

    # Strict customer cart isolation: clear cart if different customer logs in
    cart_user_id = session.get('cart_user_id')
    if cart_user_id is not None and cart_user_id != curr_user.id:
        session.pop('costume_cart', None)
        session.pop('applied_coupon', None)
        session['cart_user_id'] = curr_user.id
        session.modified = True
    elif cart_user_id is None:
        session['cart_user_id'] = curr_user.id

    raw_cart = session.get('costume_cart', {})
    cart_items = []
    subtotal = 0.0
    items_to_remove = []
    cart_modified = False

    for key, item in list(raw_cart.items()):
        variant_id = item.get('variant_id')
        prod_id = item.get('product_id')

        try:
            qty = int(item.get('quantity', 1))
        except (ValueError, TypeError):
            items_to_remove.append(key)
            continue

        # Key and ID consistency check
        if not variant_id:
            items_to_remove.append(key)
            continue

        if '_' in str(key):
            try:
                parts = str(key).split('_')
                if len(parts) != 2 or parts[1] != str(variant_id) or (prod_id and parts[0] != str(prod_id)):
                    items_to_remove.append(key)
                    continue
            except Exception:
                items_to_remove.append(key)
                continue
        elif str(key) != str(variant_id):
            items_to_remove.append(key)
            continue

        variant = db.session.get(ProductVariant, variant_id)
        if not variant or not variant.is_active:
            items_to_remove.append(key)
            continue

        product = variant.product
        if not product or not product.is_active:
            items_to_remove.append(key)
            continue

        # Strict consistency check between variant and product
        if prod_id and prod_id != product.id:
            items_to_remove.append(key)
            continue

        if not is_category_visible(product.category):
            items_to_remove.append(key)
            continue

        available_stock = variant.stock_quantity
        if available_stock <= 0:
            items_to_remove.append(key)
            continue

        if qty < 1:
            qty = 1
            item['quantity'] = 1
            cart_modified = True

        if qty > available_stock:
            qty = available_stock
            item['quantity'] = qty
            cart_modified = True

        unit_price = variant.effective_price
        line_total = round(unit_price * qty, 2)
        subtotal += line_total

        cart_items.append({
            'cart_key': key,
            'product_id': product.id,
            'product_name': product.name,
            'product_slug': product.slug,
            'variant_id': variant.id,
            'size': variant.size,
            'colour': variant.colour,
            'colour_code': variant.colour_code,
            'unit_price': unit_price,
            'base_price': product.base_price,
            'quantity': qty,
            'line_total': line_total,
            'image_url': product.primary_image,
            'stock_available': available_stock
        })

    # Clean up obsolete cart items
    if items_to_remove:
        for k in items_to_remove:
            raw_cart.pop(k, None)
        cart_modified = True

    if cart_modified:
        session['costume_cart'] = raw_cart
        session.modified = True

    subtotal = round(subtotal, 2)

    # Coupon Calculation
    coupon_code = session.get('applied_coupon')
    discount_amount = 0.0
    coupon_obj = None
    coupon_error = None

    if coupon_code:
        coupon_obj = Coupon.query.filter_by(code=coupon_code).first()
        if coupon_obj:
            valid, msg = coupon_obj.is_valid_for(subtotal)
            if valid:
                discount_amount = coupon_obj.calculate_discount(subtotal)
            else:
                session.pop('applied_coupon', None)
                coupon_error = msg
        else:
            session.pop('applied_coupon', None)

    # Delivery Charges
    delivery_charge_setting = float(StoreSetting.get('delivery_charge', '99.0'))
    free_threshold = float(StoreSetting.get('free_delivery_threshold', '1499.0'))

    if subtotal == 0 or subtotal >= free_threshold:
        delivery_fee = 0.0
    else:
        delivery_fee = delivery_charge_setting

    total_amount = max(0.0, round(subtotal - discount_amount + delivery_fee, 2))

    return {
        'items': cart_items,
        'item_count': sum(i['quantity'] for i in cart_items),
        'subtotal': subtotal,
        'discount_amount': round(discount_amount, 2),
        'delivery_fee': round(delivery_fee, 2),
        'total_amount': total_amount,
        'coupon_code': session.get('applied_coupon'),
        'coupon_error': coupon_error,
        'free_delivery_threshold': free_threshold,
        'free_delivery_progress': min(100, int((subtotal / free_threshold) * 100)) if free_threshold > 0 else 100
    }


# ------------------------------------------------------------------------------
# CONTEXT PROCESSOR (INJECTS STORE DATA ON ALL TEMPLATES)
# ------------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    cart_count = 0
    if 'costume_cart' in session:
        cart_count = sum(item.get('quantity', 0) for item in session['costume_cart'].values())

    wishlist_count = 0
    curr_user = get_current_user()
    if curr_user:
        wishlist_count = Wishlist.query.filter_by(user_id=curr_user.id).count()

    nav_categories = Category.query.filter_by(
        parent_id=None, is_active=True, is_visible_on_storefront=True
    ).order_by(Category.display_order).all()

    store_settings = {
        'name': StoreSetting.get('store_name', 'COSTUME STORE'),
        'tagline': StoreSetting.get('tagline', 'Premium Costumes, Cosplay & Theatrical Sales'),
        'phone': StoreSetting.get('contact_phone', '+91 98765 43210'),
        'email': StoreSetting.get('contact_email', 'support@costumestore.com'),
        'address': StoreSetting.get('address', '45 Heritage Boulevard, Fashion District, Bengaluru'),
        'cod_enabled': StoreSetting.get('cod_enabled', 'true') == 'true'
    }

    return {
        'cart_count': cart_count,
        'wishlist_count': wishlist_count,
        'nav_categories': nav_categories,
        'store_settings': store_settings,
        'current_user': curr_user,
        'is_admin': is_admin_session()
    }


# ------------------------------------------------------------------------------
# CUSTOMER FRONTEND ROUTES
# ------------------------------------------------------------------------------

@app.route('/')
def home():
    """Costume Store Modern Homepage."""
    featured_categories = Category.query.filter_by(
        parent_id=None, is_active=True, is_visible_on_storefront=True
    ).order_by(Category.display_order).all()

    base_prod_query = Product.query.join(Product.category).filter(
        Product.is_active == True,
        Category.is_visible_on_storefront == True
    )

    featured_products = base_prod_query.filter(Product.is_featured == True).order_by(desc(Product.id)).limit(8).all()
    bestseller_products = base_prod_query.filter(Product.is_bestseller == True).order_by(desc(Product.id)).limit(8).all()
    trending_products = base_prod_query.filter(Product.is_trending == True).order_by(desc(Product.id)).limit(4).all()
    new_arrivals = base_prod_query.order_by(desc(Product.created_at)).limit(8).all()

    return render_template(
        'index.html',
        featured_categories=featured_categories,
        featured_products=featured_products,
        bestsellers=bestseller_products,
        trending=trending_products,
        new_arrivals=new_arrivals
    )


@app.route('/shop')
def shop():
    """Costume catalogue with search, category filter, price, size, colour, availability, sorting, and pagination."""
    query_str = request.args.get('q', '').strip()
    category_slug = request.args.get('category', '').strip()
    size_filter = request.args.get('size', '').strip()
    colour_filter = request.args.get('colour', '').strip()
    availability_filter = request.args.get('availability', '').strip()
    sort_by = request.args.get('sort', 'newest').strip()

    try:
        min_price = float(request.args.get('min_price', 0))
    except (ValueError, TypeError):
        min_price = 0.0

    try:
        max_price = float(request.args.get('max_price', 0))
    except (ValueError, TypeError):
        max_price = 0.0

    page = request.args.get('page', 1, type=int)
    per_page = 12

    # Query only active products belonging to customer-visible categories
    product_query = Product.query.join(Product.category).filter(
        Product.is_active == True,
        Category.is_visible_on_storefront == True
    )

    # Search filter
    if query_str:
        product_query = product_query.filter(
            or_(
                Product.name.ilike(f'%{query_str}%'),
                Product.description.ilike(f'%{query_str}%'),
                Product.brand.ilike(f'%{query_str}%')
            )
        )

    # Category filter
    current_category = None
    if category_slug:
        cat = Category.query.filter_by(slug=category_slug).first()
        if cat and is_category_visible(cat):
            current_category = cat
            sub_ids = [s.id for s in cat.subcategories if is_category_visible(s)]
            category_ids = [cat.id] + sub_ids
            product_query = product_query.filter(
                or_(
                    Product.category_id.in_(category_ids),
                    Product.subcategory_id.in_(category_ids)
                )
            )
        else:
            abort(404)

    # Availability filter
    if availability_filter == 'in_stock':
        product_query = product_query.join(Product.variants).filter(
            ProductVariant.is_active == True,
            ProductVariant.stock_quantity > 0
        ).distinct()

    # Price range filter
    if min_price > 0:
        product_query = product_query.filter(
            func.coalesce(Product.discount_price, Product.base_price) >= min_price
        )
    if max_price > 0:
        product_query = product_query.filter(
            func.coalesce(Product.discount_price, Product.base_price) <= max_price
        )

    # Size filter
    if size_filter:
        product_query = product_query.join(Product.variants).filter(
            ProductVariant.size == size_filter,
            ProductVariant.is_active == True,
            ProductVariant.stock_quantity > 0
        ).distinct()

    # Colour filter
    if colour_filter:
        product_query = product_query.join(Product.variants).filter(
            ProductVariant.colour.ilike(f'%{colour_filter}%'),
            ProductVariant.is_active == True,
            ProductVariant.stock_quantity > 0
        ).distinct()

    # Sorting
    if sort_by == 'price_asc':
        product_query = product_query.order_by(func.coalesce(Product.discount_price, Product.base_price).asc())
    elif sort_by == 'price_desc':
        product_query = product_query.order_by(func.coalesce(Product.discount_price, Product.base_price).desc())
    elif sort_by == 'popular':
        product_query = product_query.order_by(Product.is_bestseller.desc(), Product.id.desc())
    elif sort_by == 'featured':
        product_query = product_query.order_by(Product.is_featured.desc(), Product.id.desc())
    else:  # newest
        product_query = product_query.order_by(Product.created_at.desc())

    paginated_products = product_query.paginate(page=page, per_page=per_page, error_out=False)

    # Filter metadata for toolbar: only visible categories
    all_categories = Category.query.filter_by(
        parent_id=None, is_active=True, is_visible_on_storefront=True
    ).order_by(Category.display_order).all()
    available_sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'Free Size', '2-3 Yrs', '4-5 Yrs', '6-7 Yrs', '8-10 Yrs']
    available_colours = ['Red', 'Maroon', 'Gold', 'Green', 'Yellow', 'Blue', 'Pink', 'Purple', 'White', 'Black']

    return render_template(
        'shop.html',
        products=paginated_products.items,
        pagination=paginated_products,
        current_category=current_category,
        categories=all_categories,
        available_sizes=available_sizes,
        available_colours=available_colours,
        query_str=query_str,
        category_slug=category_slug,
        size_filter=size_filter,
        colour_filter=colour_filter,
        availability_filter=availability_filter,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by
    )


@app.route('/category/<slug>')
def category_view(slug):
    """Direct route for top-level category pages."""
    category = Category.query.filter_by(slug=slug).first_or_404()
    if not is_category_visible(category):
        abort(404)
    return redirect(url_for('shop', category=slug))


@app.route('/product/<int:product_id>')
def product_details(product_id):
    """Product detail page with full variant selector, gallery, reviews, and related products."""
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    if not is_category_visible(product.category):
        abort(404)

    # Related products from same category (must be active and visible on storefront)
    related_products = Product.query.join(Product.category).filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.is_active == True,
        Category.is_visible_on_storefront == True
    ).limit(4).all()

    # Check if in user wishlist
    in_wishlist = False
    curr_user = get_current_user()
    if curr_user:
        in_wishlist = Wishlist.query.filter_by(user_id=curr_user.id, product_id=product.id).first() is not None

    return render_template(
        'product_details.html',
        product=product,
        related_products=related_products,
        in_wishlist=in_wishlist
    )


@app.route('/product/<slug>')
def product_details_by_slug(slug):
    """Support accessing product detail by URL slug."""
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    if not is_category_visible(product.category):
        abort(404)
    return redirect(url_for('product_details', product_id=product.id))


@app.route('/product/<int:product_id>/review', methods=['POST'])
@customer_required
def add_review(product_id):
    product = Product.query.get_or_404(product_id)
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()

    if not rating or rating < 1 or rating > 5:
        flash('Please select a star rating between 1 and 5.', 'error')
        return redirect(url_for('product_details', product_id=product_id))

    curr_user = get_current_user()
    review = ProductReview.query.filter_by(product_id=product.id, user_id=curr_user.id).first()
    if review:
        review.rating = rating
        review.comment = comment
        review.created_at = datetime.utcnow()
        flash('Your review has been updated!', 'success')
    else:
        review = ProductReview(
            product_id=product.id,
            user_id=curr_user.id,
            rating=rating,
            comment=comment
        )
        db.session.add(review)
        flash('Thank you for your review!', 'success')

    db.session.commit()
    return redirect(url_for('product_details', product_id=product_id))


# ------------------------------------------------------------------------------
# SHOPPING CART & COUPONS
# ------------------------------------------------------------------------------

@app.route('/cart')
def cart():
    """Full responsive shopping cart page."""
    cart_data = get_cart_data()
    return render_template('cart.html', cart=cart_data)


@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    """Adds a validated product variant to the cart. Requires active customer login."""
    curr_user = get_current_user()
    if not curr_user or curr_user.is_admin:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({
                'success': False,
                'login_required': True,
                'redirect': url_for('login', next=request.referrer or url_for('cart'))
            }), 401
        flash('Please sign in to add items to your shopping bag.', 'error')
        return redirect(url_for('login', next=request.referrer or url_for('shop')))

    session['cart_user_id'] = curr_user.id

    product_id = request.form.get('product_id', type=int)
    submitted_variant_id = request.form.get('variant_id', type=int)
    size = request.form.get('size', '').strip()
    colour = request.form.get('colour', '').strip()
    quantity = request.form.get('quantity', 1, type=int)

    if quantity < 1:
        quantity = 1

    if not product_id:
        flash('Product not available.', 'error')
        return redirect(url_for('shop'))

    product = Product.query.filter_by(id=product_id, is_active=True).first()
    if not product or not is_category_visible(product.category):
        flash('Product not available.', 'error')
        return redirect(url_for('shop'))

    # Locate and validate the variant strictly
    variant = None
    if submitted_variant_id:
        v = db.session.get(ProductVariant, submitted_variant_id)
        # Verify variant exists, is active, and strictly belongs to the submitted product
        if not v or v.product_id != product.id or not v.is_active:
            flash('Invalid product variant selection for this product.', 'error')
            return redirect(url_for('product_details', product_id=product.id))
        variant = v
    elif size and colour:
        variant = ProductVariant.query.filter_by(
            product_id=product.id,
            size=size,
            colour=colour,
            is_active=True
        ).first()

    if not variant or variant.product_id != product.id or not variant.is_active:
        flash('Please select a valid size and colour variant.', 'error')
        return redirect(url_for('product_details', product_id=product.id))

    if variant.stock_quantity < 1:
        flash(f'Sorry, {product.name} ({variant.size} / {variant.colour}) is currently out of stock.', 'error')
        return redirect(url_for('product_details', product_id=product.id))

    if 'costume_cart' not in session:
        session['costume_cart'] = {}

    cart_dict = session['costume_cart']
    cart_key = str(variant.id)

    current_qty = cart_dict.get(cart_key, {}).get('quantity', 0)
    new_qty = current_qty + quantity

    if new_qty > variant.stock_quantity:
        new_qty = variant.stock_quantity
        flash(f'Maximum available stock ({variant.stock_quantity}) added to cart.', 'warning')
    else:
        flash(f'"{product.name}" ({variant.size}, {variant.colour}) added to your bag.', 'success')

    cart_dict[cart_key] = {
        'product_id': product.id,
        'variant_id': variant.id,
        'quantity': new_qty
    }
    session['costume_cart'] = cart_dict
    session.modified = True

    if request.form.get('buy_now'):
        return redirect(url_for('checkout'))

    return redirect(request.referrer or url_for('cart'))


@app.route('/cart/update', methods=['POST'])
def update_cart():
    """Updates line item quantity in the cart."""
    cart_key = request.form.get('cart_key')
    action = request.form.get('action')
    raw_cart = session.get('costume_cart', {})

    if cart_key in raw_cart:
        item = raw_cart[cart_key]
        var_id = item.get('variant_id')
        if not var_id:
            try:
                var_id = int(str(cart_key).split('_')[-1])
            except (ValueError, IndexError):
                var_id = None
        variant = db.session.get(ProductVariant, var_id) if var_id else None
        if not variant:
            del raw_cart[cart_key]
        else:
            current_qty = raw_cart[cart_key].get('quantity', 1)
            if action == 'increase':
                if current_qty < variant.stock_quantity:
                    raw_cart[cart_key]['quantity'] = current_qty + 1
                else:
                    flash(f'Only {variant.stock_quantity} units available in stock.', 'warning')
            elif action == 'decrease':
                if current_qty > 1:
                    raw_cart[cart_key]['quantity'] = current_qty - 1
                else:
                    del raw_cart[cart_key]
            elif action == 'set':
                try:
                    new_val = int(request.form.get('quantity', 1))
                    if new_val <= 0:
                        del raw_cart[cart_key]
                    else:
                        raw_cart[cart_key]['quantity'] = min(new_val, variant.stock_quantity)
                except ValueError:
                    pass

        session['costume_cart'] = raw_cart
        session.modified = True

    return redirect(url_for('cart'))


@app.route('/cart/remove/<cart_key>', methods=['POST', 'GET'])
def remove_from_cart(cart_key):
    """Removes a variant from the cart."""
    raw_cart = session.get('costume_cart', {})
    if str(cart_key) in raw_cart:
        del raw_cart[str(cart_key)]
        session['costume_cart'] = raw_cart
        session.modified = True
        flash('Item removed from cart.', 'success')
    return redirect(url_for('cart'))


@app.route('/cart/clear', methods=['POST'])
def clear_cart():
    session.pop('costume_cart', None)
    session.pop('applied_coupon', None)
    flash('Your cart has been cleared.', 'info')
    return redirect(url_for('cart'))


@app.route('/cart/apply-coupon', methods=['POST'])
def apply_coupon():
    code = (request.form.get('coupon_code') or '').strip().upper()
    if not code:
        flash('Please enter a coupon code.', 'error')
        return redirect(url_for('cart'))

    coupon = Coupon.query.filter_by(code=code).first()
    if not coupon:
        flash('Invalid coupon code.', 'error')
        return redirect(url_for('cart'))

    cart_data = get_cart_data()
    valid, message = coupon.is_valid_for(cart_data['subtotal'])
    if not valid:
        flash(message, 'error')
        return redirect(url_for('cart'))

    session['applied_coupon'] = coupon.code
    flash(f'Coupon "{coupon.code}" applied successfully! You saved ₹{coupon.calculate_discount(cart_data["subtotal"]):.2f}.', 'success')
    return redirect(url_for('cart'))


@app.route('/cart/remove-coupon', methods=['POST'])
def remove_coupon():
    session.pop('applied_coupon', None)
    flash('Coupon removed.', 'info')
    return redirect(url_for('cart'))


# ------------------------------------------------------------------------------
# CHECKOUT & PAYMENT INTEGRATION (RAZORPAY & COD)
# ------------------------------------------------------------------------------

def _razorpay_credentials():
    key_id = (app.config.get('RAZORPAY_KEY_ID') or os.environ.get('RAZORPAY_KEY_ID') or '').strip()
    key_secret = (app.config.get('RAZORPAY_KEY_SECRET') or os.environ.get('RAZORPAY_KEY_SECRET') or '').strip()
    return key_id, key_secret


def _create_razorpay_order(amount_paise, receipt):
    key_id, key_secret = _razorpay_credentials()
    if not key_id or not key_secret:
        raise RuntimeError('Razorpay keys are not configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env.')

    payload = json.dumps({
        'amount': int(amount_paise),
        'currency': 'INR',
        'receipt': str(receipt)[:40],
        'payment_capture': 1
    }).encode('utf-8')

    auth = base64.b64encode(f'{key_id}:{key_secret}'.encode()).decode()
    req = urllib.request.Request(
        'https://api.razorpay.com/v1/orders',
        data=payload,
        method='POST',
        headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        app.logger.error('Razorpay order creation error: %s', detail)
        raise RuntimeError('Razorpay could not create the payment order. Please verify your API credentials.')


@app.route('/checkout')
def checkout():
    """Checkout page: shipping details, order review, payment method selection."""
    if is_admin_session():
        flash('Admins cannot purchase products.', 'error')
        return redirect(url_for('shop'))

    cart_data = get_cart_data()
    if not cart_data['items']:
        flash('Your shopping bag is empty.', 'error')
        return redirect(url_for('shop'))

    curr_user = get_current_user()
    default_address = None
    if curr_user:
        default_address = curr_user.default_address

    return render_template(
        'checkout.html',
        cart=cart_data,
        user=curr_user,
        default_address=default_address
    )


@app.route('/checkout/process', methods=['POST'])
def process_checkout():
    """Processes customer checkout, validates stock, initiates Razorpay or places COD order."""
    if is_admin_session():
        flash('Admins cannot place orders.', 'error')
        return redirect(url_for('shop'))

    # Strict server-side re-check of original requested cart quantities against live stock
    raw_cart = session.get('costume_cart', {})
    for k, raw_item in raw_cart.items():
        v = db.session.get(ProductVariant, raw_item.get('variant_id'))
        req_qty = int(raw_item.get('quantity', 1))
        if not v or not v.is_active or v.stock_quantity < req_qty:
            prod_name = v.product.name if (v and v.product) else "item"
            flash(f'Stock changed for "{prod_name}". Please review your cart.', 'error')
            return redirect(url_for('cart'))

    cart_data = get_cart_data()
    if not cart_data['items']:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('cart'))

    # Extract & validate customer information
    full_name = (request.form.get('full_name') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    phone = re.sub(r'\D', '', request.form.get('phone') or '')
    address = (request.form.get('shipping_address') or '').strip()
    city = (request.form.get('city') or '').strip()
    state = (request.form.get('state') or '').strip()
    pincode = (request.form.get('pincode') or '').strip()
    payment_method = request.form.get('payment_method', 'razorpay')
    notes = (request.form.get('notes') or '').strip()

    if len(full_name) < 2 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        flash('Please provide a valid full name and email address.', 'error')
        return redirect(url_for('checkout'))

    if len(phone) < 10 or len(address) < 5 or not city or not state or len(pincode) < 6:
        flash('Please fill in complete delivery address details.', 'error')
        return redirect(url_for('checkout'))

    # Strict server-side re-check of stock, variant consistency, and category visibility for each line item
    snapshot = []
    for item in cart_data['items']:
        variant = db.session.get(ProductVariant, item['variant_id'])
        if not variant or not variant.is_active or variant.stock_quantity < item['quantity']:
            flash(f'Stock changed for "{item["product_name"]}". Please review your cart.', 'error')
            return redirect(url_for('cart'))

        product = variant.product
        if not product or not product.is_active or product.id != item['product_id'] or not is_category_visible(product.category):
            flash(f'Product "{item["product_name"]}" is no longer available.', 'error')
            return redirect(url_for('cart'))

        snapshot.append({
            'product_id': item['product_id'],
            'variant_id': item['variant_id'],
            'product_name': item['product_name'],
            'size': item['size'],
            'colour': item['colour'],
            'unit_price': item['unit_price'],
            'quantity': item['quantity'],
            'line_total': item['line_total'],
            'image_url': item['image_url']
        })

    subtotal = cart_data['subtotal']
    discount_amount = cart_data['discount_amount']
    delivery_fee = cart_data['delivery_fee']
    total_amount = cart_data['total_amount']
    coupon_code = cart_data['coupon_code']
    curr_user = get_current_user()
    customer_id = curr_user.id if curr_user and not curr_user.is_admin else None

    # Automatically save / update customer address for registered users
    if curr_user and not curr_user.is_admin:
        user_addr = curr_user.default_address
        if not user_addr:
            user_addr = Address(
                user_id=curr_user.id,
                full_name=full_name,
                phone=phone,
                street_address=address,
                city=city,
                state=state,
                pincode=pincode,
                is_default=True
            )
            db.session.add(user_addr)
        else:
            user_addr.full_name = full_name
            user_addr.phone = phone
            user_addr.street_address = address
            user_addr.city = city
            user_addr.state = state
            user_addr.pincode = pincode
        curr_user.address = f"{address}, {city}, {state} - {pincode}"
        curr_user.phone = phone

    # Order Number Generation
    order_number = f"CST-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{int(datetime.utcnow().timestamp()) % 1000:03d}"

    # Handle Cash on Delivery (COD)
    if payment_method == 'cod':
        if StoreSetting.get('cod_enabled', 'true') != 'true':
            flash('Cash on Delivery is currently disabled.', 'error')
            return redirect(url_for('checkout'))

        try:
            # Create the confirmed order
            new_order = Order(
                order_number=order_number,
                customer_id=customer_id,
                full_name=full_name,
                email=email,
                phone=phone,
                shipping_address=address,
                city=city,
                state=state,
                pincode=pincode,
                subtotal=subtotal,
                discount_amount=discount_amount,
                coupon_code=coupon_code,
                delivery_fee=delivery_fee,
                total_amount=total_amount,
                payment_method='cod',
                payment_status='pending',
                order_status='Confirmed',
                notes=notes
            )
            db.session.add(new_order)
            db.session.flush()

            # Create Order Items & deduct inventory atomically
            for item in snapshot:
                order_item = OrderItem(
                    order_id=new_order.id,
                    product_id=item['product_id'],
                    variant_id=item['variant_id'],
                    product_name=item['product_name'],
                    size=item['size'],
                    colour=item['colour'],
                    unit_price=item['unit_price'],
                    quantity=item['quantity'],
                    total_price=item['line_total'],
                    image_url=item['image_url']
                )
                db.session.add(order_item)

                # Deduct inventory
                var = db.session.get(ProductVariant, item['variant_id'])
                var.stock_quantity = max(0, var.stock_quantity - item['quantity'])

            # Update coupon usage
            if coupon_code:
                c = Coupon.query.filter_by(code=coupon_code).first()
                if c:
                    c.times_used += 1

            db.session.commit()

            # Clear cart session
            session.pop('costume_cart', None)
            session.pop('applied_coupon', None)

            # Dispatch Order Placed & Admin Alert Notifications
            try:
                send_order_placed_email(new_order)
                send_admin_new_order_alert(new_order)
            except Exception as e:
                app.logger.warning(f"Error dispatching order confirmation email: {e}")

            return render_template(
                'payment_result.html',
                success=True,
                message='Your order has been placed successfully via Cash on Delivery!',
                order=new_order
            )
        except Exception as exc:
            db.session.rollback()
            app.logger.exception('COD order creation failed')
            flash('Error placing order: ' + str(exc), 'error')
            return redirect(url_for('checkout'))

    # Handle Razorpay Online Payment
    amount_paise = int(round(total_amount * 100))
    if amount_paise <= 0:
        flash('Payment amount must be greater than zero.', 'error')
        return redirect(url_for('cart'))

    try:
        gateway_order = _create_razorpay_order(amount_paise, order_number)

        # Store full order intent in PaymentTransaction
        order_intent = {
            'order_number': order_number,
            'customer_id': customer_id,
            'full_name': full_name,
            'email': email,
            'phone': phone,
            'shipping_address': address,
            'city': city,
            'state': state,
            'pincode': pincode,
            'subtotal': subtotal,
            'discount_amount': discount_amount,
            'coupon_code': coupon_code,
            'delivery_fee': delivery_fee,
            'total_amount': total_amount,
            'notes': notes,
            'snapshot': snapshot
        }

        txn = PaymentTransaction(
            gateway_order_id=gateway_order['id'],
            customer_id=customer_id or 0,
            order_type='costume',
            amount_paise=amount_paise,
            cart_json=json.dumps(order_intent),
            status='created'
        )
        db.session.add(txn)
        db.session.commit()

        key_id, _ = _razorpay_credentials()
        customer_info = {'name': full_name, 'email': email, 'phone': phone}

        return render_template(
            'payment_gateway.html',
            key_id=key_id,
            gateway_order_id=gateway_order['id'],
            amount_paise=amount_paise,
            customer=customer_info,
            order_number=order_number
        )
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('Could not initiate Razorpay checkout')
        flash(str(exc), 'error')
        return redirect(url_for('checkout'))


def _fulfill_confirmed_payment(txn, payment_id, signature=None):
    """
    Idempotent helper to fulfill a cryptographically confirmed Razorpay payment.
    Creates Order and OrderItem records, deducts inventory atomically,
    updates coupon usage, sets PaymentTransaction to 'paid', and sends email.
    If already fulfilled (status == 'paid'), returns existing order cleanly.
    """
    if txn.status == 'paid' and txn.order_id:
        return db.session.get(Order, txn.order_id)

    data = json.loads(txn.cart_json)
    snapshot = data.get('snapshot', [])

    # Re-verify stock before final deduction
    for item in snapshot:
        var = db.session.get(ProductVariant, item['variant_id'])
        if not var or var.stock_quantity < item['quantity']:
            raise RuntimeError(f'Stock became unavailable for {item["product_name"]}. Please contact support.')

    order = Order(
        order_number=data['order_number'],
        customer_id=data['customer_id'] if data['customer_id'] != 0 else None,
        full_name=data['full_name'],
        email=data['email'],
        phone=data['phone'],
        shipping_address=data['shipping_address'],
        city=data['city'],
        state=data['state'],
        pincode=data['pincode'],
        subtotal=data['subtotal'],
        discount_amount=data['discount_amount'],
        coupon_code=data['coupon_code'],
        delivery_fee=data['delivery_fee'],
        total_amount=data['total_amount'],
        payment_method='razorpay',
        payment_status='paid',
        order_status='Processing',
        notes=data.get('notes')
    )
    db.session.add(order)
    db.session.flush()

    for item in snapshot:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item['product_id'],
            variant_id=item['variant_id'],
            product_name=item['product_name'],
            size=item['size'],
            colour=item['colour'],
            unit_price=item['unit_price'],
            quantity=item['quantity'],
            total_price=item['line_total'],
            image_url=item['image_url']
        )
        db.session.add(order_item)

        var = db.session.get(ProductVariant, item['variant_id'])
        var.stock_quantity = max(0, var.stock_quantity - item['quantity'])

    if data.get('coupon_code'):
        c = Coupon.query.filter_by(code=data['coupon_code']).first()
        if c:
            c.times_used += 1

    txn.gateway_payment_id = payment_id
    if signature:
        txn.signature = signature
    txn.status = 'paid'
    txn.order_id = order.id
    db.session.commit()

    try:
        send_payment_received_email(order, transaction_id=payment_id)
        send_admin_new_order_alert(order)
    except Exception as e:
        app.logger.warning(f"Error dispatching payment confirmation email: {e}")
    return order


@app.route('/payment/verify', methods=['POST'])
def verify_payment():
    """Verifies Razorpay HMAC signature on backend, deducts inventory, creates Order & OrderItem."""
    gateway_order_id = request.form.get('razorpay_order_id', '').strip()
    payment_id = request.form.get('razorpay_payment_id', '').strip()
    signature = request.form.get('razorpay_signature', '').strip()

    if not gateway_order_id or not payment_id or not signature:
        return render_template(
            'payment_result.html',
            success=False,
            message='Missing payment gateway confirmation parameters. Your cart is unchanged.'
        )

    txn = PaymentTransaction.query.filter_by(gateway_order_id=gateway_order_id).first()
    if not txn:
        return render_template(
            'payment_result.html',
            success=False,
            message='Payment transaction record not found. Please contact support.'
        )

    if txn.status == 'paid':
        existing_order = db.session.get(Order, txn.order_id) if txn.order_id else None
        return render_template(
            'payment_result.html',
            success=True,
            message='This payment has already been verified and confirmed.',
            order=existing_order
        )

    # Server-side HMAC-SHA256 signature verification
    key_id, key_secret = _razorpay_credentials()
    if not key_secret:
        return render_template(
            'payment_result.html',
            success=False,
            message='Razorpay gateway secret not configured on server. Contact store administration.'
        )

    expected_signature = hmac.new(
        key_secret.encode('utf-8'),
        f'{gateway_order_id}|{payment_id}'.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        txn.status = 'verification_failed'
        db.session.commit()
        return render_template(
            'payment_result.html',
            success=False,
            message='Payment signature verification failed. Your card was not charged.'
        )

    try:
        order = _fulfill_confirmed_payment(txn, payment_id, signature)

        # Clear shopping cart
        session.pop('costume_cart', None)
        session.pop('applied_coupon', None)

        return render_template(
            'payment_result.html',
            success=True,
            message='Payment verified successfully! Your costume order has been confirmed.',
            order=order
        )
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('Order confirmation failed after payment verification')
        return render_template(
            'payment_result.html',
            success=False,
            message=str(exc) + ' Contact store support with your Razorpay payment ID: ' + payment_id,
            payment_id=payment_id
        )


@app.route('/webhook/razorpay', methods=['POST'])
def razorpay_webhook():
    """
    Handles Razorpay Webhook events (e.g. payment.captured, payment.failed, order.paid).
    Verifies HMAC-SHA256 signature using dedicated RAZORPAY_WEBHOOK_SECRET on raw payload bytes.
    Ensures idempotent processing, safe state transitions, and avoids duplicate inventory deductions.
    """
    webhook_secret = (app.config.get('RAZORPAY_WEBHOOK_SECRET') or os.environ.get('RAZORPAY_WEBHOOK_SECRET') or '').strip()
    if not webhook_secret:
        app.logger.warning('Razorpay webhook secret not configured. Rejecting webhook.')
        return jsonify({'status': 'ignored', 'reason': 'Webhook secret not configured on server.'}), 400

    raw_payload = request.get_data()
    received_signature = request.headers.get('X-Razorpay-Signature', '')

    if not received_signature:
        return jsonify({'status': 'error', 'reason': 'Missing signature header.'}), 400

    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        raw_payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, received_signature):
        app.logger.warning('Invalid Razorpay webhook signature received.')
        return jsonify({'status': 'error', 'reason': 'Invalid webhook signature.'}), 400

    try:
        event = json.loads(raw_payload.decode('utf-8'))
    except Exception as exc:
        return jsonify({'status': 'error', 'reason': f'Invalid JSON payload: {exc}'}), 400

    event_type = event.get('event')
    payload_entity = event.get('payload', {})
    payment_obj = payload_entity.get('payment', {}).get('entity', {})
    order_obj = payload_entity.get('order', {}).get('entity', {})

    gateway_order_id = payment_obj.get('order_id') or order_obj.get('id')
    gateway_payment_id = payment_obj.get('id')

    if not gateway_order_id:
        return jsonify({'status': 'ignored', 'reason': 'No order ID found in webhook payload.'}), 200

    txn = PaymentTransaction.query.filter_by(gateway_order_id=gateway_order_id).first()
    if not txn:
        return jsonify({'status': 'ignored', 'reason': f'No local transaction for gateway order {gateway_order_id}.'}), 200

    # 1. Handle Successful Payment Captured or Order Paid
    if event_type in ['payment.captured', 'order.paid']:
        if txn.status == 'paid':
            return jsonify({'status': 'already_processed', 'order_id': txn.order_id}), 200

        try:
            order = _fulfill_confirmed_payment(txn, gateway_payment_id or 'webhook_captured')
            return jsonify({
                'status': 'success',
                'order_id': order.id,
                'order_number': order.order_number
            }), 200
        except Exception as exc:
            db.session.rollback()
            app.logger.exception('Webhook order fulfillment error')
            return jsonify({'status': 'error', 'reason': str(exc)}), 500

    # 2. Handle Failed Payment Event
    elif event_type == 'payment.failed':
        # NEVER downgrade an already paid order!
        if txn.status == 'paid':
            app.logger.info('Ignoring payment.failed webhook event because transaction is already marked paid.')
            return jsonify({'status': 'ignored', 'reason': 'Transaction is already confirmed and paid.'}), 200

        txn.status = 'failed'
        if gateway_payment_id:
            txn.gateway_payment_id = gateway_payment_id
        db.session.commit()
        return jsonify({'status': 'failed_recorded', 'gateway_order_id': gateway_order_id}), 200

    # 3. Other events (acknowledged safely)
    return jsonify({'status': 'acknowledged', 'event': event_type}), 200


@app.route('/payment/cancel')
def payment_cancel():
    return render_template(
        'payment_result.html',
        success=False,
        message='Payment was cancelled. Your shopping bag has been saved so you can try again.'
    )


# ------------------------------------------------------------------------------
# CUSTOMER ACCOUNT & PROFILE
# ------------------------------------------------------------------------------

@app.route('/profile')
@customer_required
def profile():
    """Customer account dashboard with personal details, order summary, and review history."""
    curr_user = get_current_user()
    recent_orders = Order.query.filter_by(customer_id=curr_user.id).order_by(desc(Order.created_at)).limit(5).all()
    wishlist_items = Wishlist.query.filter_by(user_id=curr_user.id).limit(4).all()
    addresses = curr_user.addresses
    reviews = ProductReview.query.filter_by(user_id=curr_user.id).order_by(desc(ProductReview.created_at)).all()
    active_tab = request.args.get('tab', 'overview')

    return render_template(
        'profile.html',
        user=curr_user,
        recent_orders=recent_orders,
        wishlist_items=wishlist_items,
        addresses=addresses,
        reviews=reviews,
        active_tab=active_tab
    )


@app.route('/profile/edit', methods=['POST'])
@customer_required
def edit_profile():
    curr_user = get_current_user()
    name = (request.form.get('name') or '').strip()
    phone = re.sub(r'\D', '', request.form.get('phone') or '')
    address = (request.form.get('address') or '').strip()

    if len(name) < 2:
        flash('Please enter a valid name.', 'error')
        return redirect(url_for('profile'))

    curr_user.name = name
    if phone:
        curr_user.phone = phone
    if address:
        curr_user.address = address

    db.session.commit()
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('profile'))


@app.route('/profile/change-password', methods=['POST'])
@customer_required
def change_password():
    curr_user = get_current_user()
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if not curr_user.check_password(current_pw):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('profile'))

    if new_pw != confirm_pw:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('profile'))

    if not valid_password(new_pw):
        flash('New password must be at least 8 characters and include uppercase, lowercase, number, and special symbol.', 'error')
        return redirect(url_for('profile'))

    curr_user.set_password(new_pw)
    db.session.commit()
    flash('Password changed successfully.', 'success')
    return redirect(url_for('profile'))


@app.route('/profile/delete-account/request-otp', methods=['POST'])
@app.route('/account/delete/request-otp', methods=['POST'])
@customer_required
def delete_account_request_otp():
    """Generates a secure 6-digit OTP and emails it to the customer for account deletion."""
    curr_user = get_current_user()
    if not curr_user or curr_user.is_admin:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Administrator accounts cannot be deleted through this workflow.'}), 403
        flash('Administrator accounts cannot be deleted through this workflow.', 'error')
        return redirect(url_for('profile'))

    # Cooldown check: 60 seconds between OTP requests
    recent_token = OtpToken.query.filter_by(
        user_id=curr_user.id,
        token_type='account_deletion'
    ).order_by(OtpToken.created_at.desc()).first()

    if recent_token and not recent_token.is_used:
        elapsed = (datetime.utcnow() - recent_token.created_at).total_seconds()
        if elapsed < 60:
            remaining = int(60 - elapsed)
            msg = f"Please wait {remaining} seconds before requesting another verification code."
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': msg}), 429
            flash(msg, 'warning')
            return redirect(url_for('profile', show_delete_modal='1'))

    # Invalidate prior unused deletion tokens for this user
    OtpToken.query.filter_by(
        user_id=curr_user.id,
        token_type='account_deletion',
        is_used=False
    ).update({'is_used': True})

    # Generate 6-digit numeric OTP and compute HMAC verifier
    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    otp_hash = generate_otp_verifier(curr_user.id, curr_user.email, 'account_deletion', otp_code)

    token_record = OtpToken(
        user_id=curr_user.id,
        email=curr_user.email,
        token_hash=otp_hash,
        token_type='account_deletion',
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        max_attempts=3
    )
    db.session.add(token_record)
    db.session.commit()

    # Dispatch email
    delivery_success = False
    delivery_error = ""
    try:
        result = send_account_deletion_otp(curr_user.email, curr_user.name, otp_code)
        if result:
            delivery_success = True
        else:
            delivery_error = result.message if hasattr(result, 'message') else "Failed to send email."
    except Exception as exc:
        app.logger.warning(f"Error sending deletion OTP to {curr_user.email}: {exc}")
        delivery_error = str(exc)

    if not delivery_success:
        # Invalidate unrevealed token so no active undisclosed challenge exists
        try:
            db.session.delete(token_record)
            db.session.commit()
        except Exception:
            db.session.rollback()
        err_msg = "Unable to dispatch verification code via email. Please check your email configuration or contact support."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err_msg}), 502
        flash(err_msg, 'error')
        return redirect(url_for('profile', show_delete_modal='1'))

    msg = "A 6-digit verification code has been sent and accepted by the mail server for delivery to your registered email address. It will expire in 5 minutes."
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': msg})
    flash(msg, 'info')
    return redirect(url_for('profile', show_delete_modal='1'))


@app.route('/profile/delete-account/verify-otp', methods=['POST'])
@app.route('/account/delete/verify-otp', methods=['POST'])
@customer_required
def delete_account_verify_otp():
    """Verifies OTP, anonymizes order logs for statutory compliance, and removes customer account."""
    curr_user = get_current_user()
    if not curr_user or curr_user.is_admin:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Unauthorized action.'}), 403
        flash('Unauthorized action.', 'error')
        return redirect(url_for('profile'))

    otp_input = ''
    if request.is_json:
        otp_input = request.json.get('otp', '')
    else:
        otp_input = request.form.get('otp', '')
    otp_input = re.sub(r'\D', '', str(otp_input or ''))

    if len(otp_input) != 6:
        msg = "Please enter the valid 6-digit numeric verification code."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('profile', show_delete_modal='1'))

    token_record = OtpToken.query.filter_by(
        user_id=curr_user.id,
        token_type='account_deletion',
        is_used=False
    ).order_by(OtpToken.created_at.desc()).first()

    if not token_record:
        msg = "No active deletion verification code found. Please request a new code."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('profile', show_delete_modal='1'))

    if token_record.is_expired():
        token_record.is_used = True
        db.session.commit()
        msg = "Verification code has expired. Please request a new code."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('profile', show_delete_modal='1'))

    if token_record.attempts >= token_record.max_attempts:
        token_record.is_used = True
        db.session.commit()
        msg = "Maximum verification attempts exceeded. Please request a new code."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('profile', show_delete_modal='1'))

    if not verify_otp_verifier(token_record.token_hash, curr_user.id, curr_user.email, 'account_deletion', otp_input):
        token_record.attempts += 1
        remaining = token_record.max_attempts - token_record.attempts
        if remaining <= 0:
            token_record.is_used = True
        db.session.commit()
        msg = f"Invalid verification code. {remaining} attempt(s) remaining." if remaining > 0 else "Invalid code. Maximum attempts exceeded. Please request a new code."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('profile', show_delete_modal='1'))

    # OTP is valid!
    token_record.is_used = True
    user_id = curr_user.id

    # 1. Anonymize statutory orders & payment transactions (customer_id = NULL)
    Order.query.filter_by(customer_id=user_id).update({'customer_id': None}, synchronize_session=False)
    PaymentTransaction.query.filter_by(customer_id=user_id).update({'customer_id': None}, synchronize_session=False)

    # 2. Delete customer-owned private data
    Address.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    Wishlist.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    ProductReview.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    OtpToken.query.filter_by(user_id=user_id).delete(synchronize_session=False)

    # 3. Permanently remove customer record
    db.session.delete(curr_user)
    db.session.commit()

    # 4. Invalidate session
    session.clear()

    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': 'Your account has been deleted successfully.', 'redirect_url': url_for('home')})

    flash('Your account has been deleted successfully.', 'info')
    return redirect(url_for('home'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Allows customer to request a password reset email."""
    if request.method == 'GET':
        if 'user_id' in session:
            return redirect(url_for('profile') if not is_admin_session() else url_for('admin_dashboard'))
        return render_template('forgot_password.html')

    email = (request.form.get('email') or '').strip().lower()
    if email:
        user = User.query.filter_by(email=email).first()
        if user and not user.is_admin:
            # Invalidate older password reset tokens
            OtpToken.query.filter_by(
                user_id=user.id,
                token_type='password_reset',
                is_used=False
            ).update({'is_used': True})

            raw_token = secrets.token_urlsafe(32)
            token_hash = generate_otp_verifier(user.id, user.email, 'password_reset', raw_token)
            token_record = OtpToken(
                user_id=user.id,
                email=user.email,
                token_hash=token_hash,
                token_type='password_reset',
                expires_at=datetime.utcnow() + timedelta(minutes=15),
                max_attempts=5
            )
            db.session.add(token_record)
            db.session.commit()

            reset_url = url_for('reset_password', token=raw_token, _external=True)
            try:
                send_password_reset_email(user.email, user.name, reset_url)
            except Exception as exc:
                app.logger.warning(f"Error sending password reset email to {email}: {exc}")

    # Standard anti-enumeration notice
    flash('If that email address is registered, password reset instructions have been sent.', 'info')
    return redirect(url_for('login'))


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Verifies reset token and updates account password."""
    active_tokens = OtpToken.query.filter_by(
        token_type='password_reset',
        is_used=False
    ).all()
    token_record = None
    for cand in active_tokens:
        if not cand.is_expired():
            if verify_otp_verifier(cand.token_hash, cand.user_id, cand.email, 'password_reset', token):
                token_record = cand
                break

    if not token_record or token_record.is_expired():
        flash('This password reset link is invalid or has expired. Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'GET':
        return render_template('reset_password.html', token=token)

    password = request.form.get('password') or ''
    confirm_password = request.form.get('confirm_password') or ''

    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return render_template('reset_password.html', token=token)

    if not valid_password(password):
        flash('Password must be at least 8 characters and include uppercase, lowercase, a number, and a special character.', 'error')
        return render_template('reset_password.html', token=token)

    user = User.query.get(token_record.user_id)
    if not user:
        flash('Account not found.', 'error')
        return redirect(url_for('forgot_password'))

    user.set_password(password)
    token_record.is_used = True
    # Invalidate all other reset tokens for this user
    OtpToken.query.filter_by(user_id=user.id, token_type='password_reset').update({'is_used': True})
    db.session.commit()

    flash('Your password has been reset successfully. Please sign in with your new password.', 'success')
    return redirect(url_for('login'))


@app.route('/orders')
@customer_required
def my_orders():
    """Customer order history page."""
    curr_user = get_current_user()
    page = request.args.get('page', 1, type=int)
    paginated_orders = Order.query.filter_by(customer_id=curr_user.id).order_by(desc(Order.created_at)).paginate(page=page, per_page=10, error_out=False)
    return render_template('orders.html', orders=paginated_orders.items, pagination=paginated_orders)


@app.route('/order-history')
@customer_required
def order_history():
    """Alias for customer order history."""
    return redirect(url_for('my_orders'))


@app.route('/orders/<int:order_id>')
@customer_required
def order_detail(order_id):
    """Customer order tracking and item breakdown."""
    curr_user = get_current_user()
    order = Order.query.filter_by(id=order_id, customer_id=curr_user.id).first_or_404()
    return render_template('order_details.html', order=order)


@app.route('/wishlist')
@customer_required
def wishlist():
    """Customer wishlist page."""
    curr_user = get_current_user()
    wishlist_entries = Wishlist.query.filter_by(user_id=curr_user.id).all()
    return render_template('wishlist.html', entries=wishlist_entries)


@app.route('/wishlist/toggle/<int:product_id>', methods=['POST'])
def toggle_wishlist(product_id):
    """AJAX / Form toggle product in customer wishlist."""
    curr_user = get_current_user()
    if not curr_user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please sign in to save items to your wishlist.', 'login_required': True}), 401
        flash('Please sign in to save items to your wishlist.', 'error')
        return redirect(url_for('login', next=request.referrer))

    product = Product.query.get_or_404(product_id)
    entry = Wishlist.query.filter_by(user_id=curr_user.id, product_id=product.id).first()
    if entry:
        db.session.delete(entry)
        db.session.commit()
        added = False
        msg = f'"{product.name}" removed from your wishlist.'
    else:
        new_entry = Wishlist(user_id=curr_user.id, product_id=product.id)
        db.session.add(new_entry)
        db.session.commit()
        added = True
        msg = f'"{product.name}" saved to your wishlist.'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        count = Wishlist.query.filter_by(user_id=curr_user.id).count()
        return jsonify({'success': True, 'added': added, 'message': msg, 'wishlist_count': count})

    flash(msg, 'success')
    return redirect(request.referrer or url_for('wishlist'))


# ------------------------------------------------------------------------------
# AUTHENTICATION (LOGIN, REGISTER, LOGOUT)
# ------------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        remember_me = bool(request.form.get('remember_me'))
        next_url = request.args.get('next') or request.form.get('next')
        client_ip = request.remote_addr or '127.0.0.1'

        if is_login_rate_limited(client_ip):
            flash('Too many failed login attempts. Please wait a few minutes before trying again.', 'error')
            return render_template('login.html', email=email)

        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('login.html', email=email)

        # Authenticate against database user (admin and customer accounts)
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            record_failed_login(client_ip)
            flash('Invalid email address or password.', 'error')
            return render_template('login.html', email=email)

        reset_failed_login(client_ip)

        # Auto-upgrade legacy hash if needed
        if not user.password.startswith(('pbkdf2:', 'scrypt:')):
            user.set_password(password)
            db.session.commit()

        if remember_me:
            session.permanent = True
            app.permanent_session_lifetime = timedelta(days=30)
        else:
            session.permanent = False

        session['user_id'] = user.id
        session['user_name'] = user.name
        session['is_admin'] = bool(user.is_admin)
        session['cart_user_id'] = user.id

        target_url = next_url if (next_url and is_safe_url(next_url)) else None

        flash(f'Welcome back, {user.name}!', 'success')
        if user.is_admin:
            return redirect(target_url or url_for('admin_dashboard'))
        return redirect(target_url or url_for('home'))

    if 'user_id' in session:
        if is_admin_session():
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('home'))

    return render_template('login.html', email='')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        if 'user_id' in session:
            if is_admin_session():
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('home'))
        return render_template('register.html', form_data={})

    # POST handling
    name = (request.form.get('name') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    raw_phone = request.form.get('phone') or ''
    phone = re.sub(r'\D', '', raw_phone)
    if phone.startswith('91') and len(phone) == 12:
        phone = phone[2:]

    street_address = (request.form.get('street_address') or request.form.get('address') or '').strip()
    state = (request.form.get('state') or '').strip()
    city = (request.form.get('city') or '').strip()
    pincode = re.sub(r'\D', '', request.form.get('pincode') or '')

    # Backwards compatibility fallback for scripts/tests passing unified address string
    if street_address and not state and not city and not pincode:
        state = 'Karnataka'
        city = 'Bengaluru Urban'
        pincode = '560001'

    password = request.form.get('password') or ''
    confirm_password = request.form.get('confirm_password') or ''

    form_data = {
        'name': name,
        'email': email,
        'phone': phone,
        'street_address': street_address,
        'state': state,
        'city': city,
        'pincode': pincode
    }

    # 1. Full Name Validation (Layered validation, min 2, max 100)
    name = normalize_full_name(name)
    valid_name, name_err = validate_full_name(name)
    if not valid_name:
        flash(f'Please provide a valid full name. {name_err}', 'error')
        return render_template('register.html', form_data=form_data)

    # 2. Email Address Validation
    if email.endswith('@localhost') or email == 'admin@localhost':
        flash('The localhost domain is reserved for local administrator provisioning and cannot be used for customer registration.', 'error')
        return render_template('register.html', form_data=form_data)

    valid_email, email_err = validate_email_address(email)
    if not valid_email:
        flash(f'Please provide a valid email address. {email_err}', 'error')
        return render_template('register.html', form_data=form_data)

    # 3. Mobile Number Validation
    if len(phone) != 10 or phone[0] not in '6789':
        flash('Please provide a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.', 'error')
        return render_template('register.html', form_data=form_data)

    # 4. Meaningful Indian Street Address Validation
    valid_addr, addr_err = validate_street_address(street_address)
    if not valid_addr:
        flash(f'Please provide complete house, building, and street address details. {addr_err}', 'error')
        return render_template('register.html', form_data=form_data)

    # 5. State / UT Validation
    if not is_valid_state(state):
        flash('Please select a valid Indian State or Union Territory.', 'error')
        return render_template('register.html', form_data=form_data)

    # 6. District Validation
    if not city or not is_valid_district(state, city):
        flash('Please select a valid District / City for the chosen State.', 'error')
        return render_template('register.html', form_data=form_data)

    # 7. PIN Code Validation
    if not is_valid_pincode(pincode, state, city):
        flash('Please provide a valid 6-digit Indian PIN Code for the selected District.', 'error')
        return render_template('register.html', form_data=form_data)

    # 8. Password Strength Validation (5 Criteria)
    if not valid_password(password):
        flash('Password must be at least 8 characters and include uppercase, lowercase, a number, and a special character.', 'error')
        return render_template('register.html', form_data=form_data)

    # 9. Password Confirmation Match
    if confirm_password and password != confirm_password:
        flash('Passwords do not match. Please re-enter your password.', 'error')
        return render_template('register.html', form_data=form_data)

    # 10. Email Uniqueness (case-insensitive)
    if User.query.filter(func.lower(User.email) == email.lower()).first():
        flash('This email address is already registered. Please sign in.', 'error')
        return render_template('register.html', form_data=form_data)

    try:
        new_user = User(
            name=name,
            email=email,
            address=f"{street_address}, {city}, {state} - {pincode}",
            phone=phone,
            password=generate_password_hash(password),
            is_admin=False
        )
        db.session.add(new_user)
        db.session.flush()

        default_addr = Address(
            user_id=new_user.id,
            full_name=name,
            phone=phone,
            street_address=street_address,
            city=city,
            state=state,
            pincode=pincode,
            is_default=True
        )
        db.session.add(default_addr)
        db.session.commit()

        try:
            send_registration_welcome_email(new_user)
        except Exception as exc:
            app.logger.warning(f"Failed to dispatch welcome email to {new_user.email}: {exc}")
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while creating your account: {str(e)}', 'error')
        return render_template('register.html', form_data=form_data)

    flash('Account created successfully! You can now log in.', 'success')
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out safely.', 'success')
    return redirect(url_for('home'))


# ------------------------------------------------------------------------------
# STATIC INFORMATIONAL PAGES
# ------------------------------------------------------------------------------

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()

        if name and email and message:
            contact_msg = ContactMessage(
                name=name,
                email=email,
                subject=subject,
                message=message,
                is_read=False,
                status='unread'
            )
            db.session.add(contact_msg)
            db.session.commit()

            admin_email = os.environ.get('SMTP_ADMIN_EMAIL', StoreSetting.get('contact_email', ''))
            send_order_email(
                admin_email,
                f"Customer Inquiry: {subject or 'Costume Store Query'} from {name}",
                f"From: {name} <{email}>\nSubject: {subject}\n\nMessage:\n{message}"
            )
            flash('Thank you! Your message has been received. Our team will get back to you shortly.', 'success')
            return redirect(url_for('contact'))
        else:
            flash('Please complete all contact form fields.', 'error')

    store_settings = {
        'address': StoreSetting.get('store_address', '14, Silk Board Junction, Hosur Main Road, Bengaluru, Karnataka 560068'),
        'phone': StoreSetting.get('contact_phone', '+91 80 4123 4567'),
        'email': StoreSetting.get('contact_email', 'support@costumestore.in')
    }
    return render_template('contact.html', store_settings=store_settings)


# ------------------------------------------------------------------------------
# ADMINISTRATOR DASHBOARD & MANAGEMENT
# ------------------------------------------------------------------------------

@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard with high-level sales KPIs, interactive sales chart, order metrics, top-selling products, and stock status."""
    dashboard_data = get_dashboard_analytics()
    initial_chart_data = get_sales_chart_data('daily')

    return render_template(
        'admin/dashboard.html',
        kpis=dashboard_data['kpis'],
        inventory=dashboard_data['inventory'],
        top_selling=dashboard_data['top_selling'],
        recent_orders=dashboard_data['recent_orders'],
        order_statuses=dashboard_data['order_statuses'],
        chart_data=initial_chart_data,
        total_revenue=dashboard_data['kpis']['total_revenue'],
        total_orders=dashboard_data['kpis']['total_orders'],
        total_customers=dashboard_data['kpis']['total_customers'],
        low_stock_variants=dashboard_data['inventory']['low_stock_variants']
    )


@app.route('/admin/api/sales-chart')
@admin_required
def admin_api_sales_chart():
    """API endpoint returning JSON sales chart data for Daily, Weekly, Monthly, Yearly periods."""
    period = (request.args.get('period') or 'daily').lower().strip()
    if period not in ['daily', 'weekly', 'monthly', 'yearly']:
        period = 'daily'
    data = get_sales_chart_data(period)
    return jsonify(data)


@app.route('/admin/sales-reports')
@admin_required
def admin_sales_reports():
    """Dedicated sales reports page with date filtering, summary KPIs, breakdowns, and exports."""
    period = (request.args.get('period') or 'month').lower().strip()
    start_date = (request.args.get('start_date') or '').strip()
    end_date = (request.args.get('end_date') or '').strip()
    sort_by = (request.args.get('sort_by') or 'revenue').lower().strip()

    report_data = get_sales_report_data(
        period=period,
        start_date_str=start_date if period == 'custom' else None,
        end_date_str=end_date if period == 'custom' else None,
        sort_by=sort_by
    )

    return render_template(
        'admin/sales_reports.html',
        report=report_data
    )


@app.route('/admin/sales-reports/export/<export_format>')
@admin_required
def admin_sales_reports_export(export_format):
    """Export sales reports in CSV, Excel (.xlsx), or PDF format preserving filters."""
    fmt = (export_format or '').lower().strip()
    if fmt not in ['csv', 'excel', 'xlsx', 'pdf']:
        abort(404)

    period = (request.args.get('period') or 'month').lower().strip()
    start_date = (request.args.get('start_date') or '').strip()
    end_date = (request.args.get('end_date') or '').strip()
    sort_by = (request.args.get('sort_by') or 'revenue').lower().strip()

    report_data = get_sales_report_data(
        period=period,
        start_date_str=start_date if period == 'custom' else None,
        end_date_str=end_date if period == 'custom' else None,
        sort_by=sort_by
    )

    date_tag = f"{report_data['start_date'].strftime('%Y%m%d')}_{report_data['end_date'].strftime('%Y%m%d')}"

    if fmt == 'csv':
        csv_bytes = generate_sales_csv(report_data)
        filename = f"sales_report_{date_tag}.csv"
        return Response(
            csv_bytes,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
    elif fmt in ['excel', 'xlsx']:
        excel_bytes = generate_sales_excel(report_data)
        filename = f"sales_report_{date_tag}.xlsx"
        return send_file(
            io.BytesIO(excel_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    elif fmt == 'pdf':
        pdf_bytes = generate_sales_pdf(report_data)
        filename = f"sales_report_{date_tag}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )


@app.route('/admin/products')
@admin_required
def admin_products():
    """Admin product catalog list."""
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id', type=int)
    search = request.args.get('search', '').strip()

    q = Product.query
    if category_id:
        q = q.filter(Product.category_id == category_id)
    if search:
        q = q.filter(or_(Product.name.ilike(f'%{search}%'), Product.sku.ilike(f'%{search}%')))

    paginated = q.order_by(desc(Product.id)).paginate(page=page, per_page=15, error_out=False)
    categories = Category.query.all()

    return render_template(
        'admin/products.html',
        products=paginated.items,
        pagination=paginated,
        categories=categories,
        selected_cat=category_id,
        search=search
    )


@app.route('/admin/contact-sheet')
@admin_required
def admin_contact_sheet():
    """Visual Contact Sheet for Product Images Quality Audit."""
    return render_template('admin/contact_sheet.html')


@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    """Create a new costume product with variants and initial gallery image."""
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        category_id = request.form.get('category_id', type=int)
        subcategory_id = request.form.get('subcategory_id', type=int) or None
        brand = (request.form.get('brand') or 'Costume Store').strip()
        base_price = request.form.get('base_price', type=float)
        discount_price = request.form.get('discount_price', type=float) or None
        sku = (request.form.get('sku') or '').strip() or f"CST-{int(datetime.utcnow().timestamp())}"
        description = (request.form.get('description') or '').strip()
        details = (request.form.get('details') or '').strip()
        is_featured = bool(request.form.get('is_featured'))
        is_bestseller = bool(request.form.get('is_bestseller'))
        is_trending = bool(request.form.get('is_trending'))

        if not name or not category_id or not base_price or not description:
            flash('Product name, category, price, and description are required.', 'error')
            return redirect(url_for('admin_add_product'))

        if sku and Product.query.filter_by(sku=sku).first():
            flash(f'SKU "{sku}" is already in use by another product.', 'error')
            return redirect(url_for('admin_add_product'))

        # Generate unique slug
        base_slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower()).strip('-')
        slug = base_slug
        c = 1
        while Product.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{c}"
            c += 1

        product = Product(
            name=name,
            slug=slug,
            category_id=category_id,
            subcategory_id=subcategory_id,
            brand=brand,
            base_price=base_price,
            discount_price=discount_price,
            sku=sku,
            description=description,
            details=details,
            is_featured=is_featured,
            is_bestseller=is_bestseller,
            is_trending=is_trending
        )
        db.session.add(product)
        db.session.flush()

        # Handle multiple image uploads or primary image URL
        files = request.files.getlist('image_files')
        single_file = request.files.get('image_file')
        if single_file and single_file not in files:
            files.append(single_file)
        image_url = (request.form.get('image_url') or '').strip()

        img_count = 0
        for f in files:
            if f and f.filename and allowed_file(f.filename):
                saved_url = storage_service.save_image(f, prefix=f"{product.id}_{int(datetime.utcnow().timestamp())}_{img_count}")
                db.session.add(ProductImage(
                    product_id=product.id,
                    image_url=saved_url,
                    is_primary=(img_count == 0),
                    display_order=img_count
                ))
                img_count += 1

        if image_url:
            db.session.add(ProductImage(
                product_id=product.id,
                image_url=image_url,
                is_primary=(img_count == 0),
                display_order=img_count
            ))
            img_count += 1

        if img_count == 0:
            db.session.add(ProductImage(
                product_id=product.id,
                image_url='/static/images/placeholder-costume.jpg',
                is_primary=True,
                display_order=0
            ))

        # Add initial variants (size, colour, stock)
        sizes = request.form.getlist('variant_size[]')
        colours = request.form.getlist('variant_colour[]')
        stocks = request.form.getlist('variant_stock[]')

        for s, col, stk in zip(sizes, colours, stocks):
            s = s.strip()
            col = col.strip()
            if s and col:
                try:
                    stk_val = int(stk)
                except (ValueError, TypeError):
                    stk_val = 0
                db.session.add(ProductVariant(
                    product_id=product.id,
                    size=s,
                    colour=col,
                    colour_code='#222222',
                    sku=f"{product.sku}-{s.replace(' ', '')}-{col[:3].upper()}",
                    stock_quantity=stk_val
                ))

        db.session.commit()
        flash(f'Product "{product.name}" created successfully.', 'success')
        return redirect(url_for('admin_edit_product', product_id=product.id))

    categories = Category.query.filter_by(parent_id=None).all()
    subcategories = Category.query.filter(Category.parent_id != None).all()
    return render_template('admin/add_product.html', categories=categories, subcategories=subcategories)


@app.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    """Edit product details, manage variants and upload gallery photos."""
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name = (request.form.get('name') or product.name or '').strip()
        product.category_id = request.form.get('category_id', type=int) or product.category_id
        product.subcategory_id = request.form.get('subcategory_id', type=int) or None
        product.brand = (request.form.get('brand') or product.brand or '').strip()
        product.base_price = request.form.get('base_price', type=float) or product.base_price
        product.discount_price = request.form.get('discount_price', type=float) or None
        product.sku = (request.form.get('sku') or product.sku or '').strip()
        product.description = (request.form.get('description') or product.description or '').strip()
        details_val = request.form.get('details')
        if details_val is not None:
            product.details = details_val.strip()
        product.is_featured = bool(request.form.get('is_featured'))
        product.is_bestseller = bool(request.form.get('is_bestseller'))
        product.is_trending = bool(request.form.get('is_trending'))
        product.is_active = bool(request.form.get('is_active'))

        db.session.commit()
        flash('Product updated successfully.', 'success')
        return redirect(url_for('admin_edit_product', product_id=product.id))

    categories = Category.query.filter_by(parent_id=None).all()
    subcategories = Category.query.filter(Category.parent_id != None).all()
    return render_template('admin/edit_product.html', product=product, categories=categories, subcategories=subcategories)


@app.route('/admin/products/toggle-publish/<int:product_id>', methods=['POST'])
@admin_required
def admin_toggle_product_publish(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    db.session.commit()
    status = "published and active on storefront" if product.is_active else "unpublished (hidden from store)"
    flash(f'Product "{product.name}" is now {status}.', 'success')
    return redirect(url_for('admin_products'))


@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    name = product.name
    # Nullify order item references to preserve completed historical orders
    OrderItem.query.filter_by(product_id=product.id).update({'product_id': None, 'variant_id': None})
    Wishlist.query.filter_by(product_id=product.id).delete()
    ProductReview.query.filter_by(product_id=product.id).delete()
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{name}" has been permanently deleted.', 'success')
    return redirect(url_for('admin_products'))


@app.route('/admin/products/<int:product_id>/variants/add', methods=['POST'])
@admin_required
def admin_add_variant(product_id):
    product = Product.query.get_or_404(product_id)
    size = (request.form.get('size') or '').strip()
    colour = (request.form.get('colour') or '').strip()
    colour_code = (request.form.get('colour_code') or '#222222').strip()
    stock_quantity = request.form.get('stock_quantity', 0, type=int)
    additional_price = request.form.get('additional_price', 0.0, type=float)

    if not size or not colour:
        flash('Size and colour are required.', 'error')
        return redirect(url_for('admin_edit_product', product_id=product.id))

    sku = f"{product.sku}-{size.replace(' ', '')}-{colour[:3].upper()}"
    new_variant = ProductVariant(
        product_id=product.id,
        size=size,
        colour=colour,
        colour_code=colour_code,
        sku=sku,
        stock_quantity=stock_quantity,
        additional_price=additional_price
    )
    db.session.add(new_variant)
    db.session.commit()
    flash(f'Variant ({size} / {colour}) added.', 'success')
    return redirect(url_for('admin_edit_product', product_id=product.id))


@app.route('/admin/products/<int:product_id>/variants/delete/<int:variant_id>', methods=['POST'])
@admin_required
def admin_delete_variant(product_id, variant_id):
    variant = ProductVariant.query.filter_by(id=variant_id, product_id=product_id).first_or_404()
    db.session.delete(variant)
    db.session.commit()
    flash('Variant deleted.', 'success')
    return redirect(url_for('admin_edit_product', product_id=product_id))


@app.route('/admin/products/<int:product_id>/images/upload', methods=['POST'])
@admin_required
def admin_upload_image(product_id):
    product = Product.query.get_or_404(product_id)
    image_url = (request.form.get('image_url') or '').strip()
    files = request.files.getlist('image_files')
    single_file = request.files.get('image_file')
    if single_file and single_file not in files:
        files.append(single_file)

    uploaded_count = 0
    curr_images = len(product.images)
    for idx, f in enumerate(files):
        if f and f.filename and allowed_file(f.filename):
            saved_url = storage_service.save_image(f, prefix=f"{product.id}_{int(datetime.utcnow().timestamp())}_{idx}")
            db.session.add(ProductImage(
                product_id=product.id,
                image_url=saved_url,
                is_primary=(curr_images + uploaded_count == 0),
                display_order=curr_images + uploaded_count
            ))
            uploaded_count += 1

    if image_url:
        db.session.add(ProductImage(
            product_id=product.id,
            image_url=image_url,
            is_primary=(curr_images + uploaded_count == 0),
            display_order=curr_images + uploaded_count
        ))
        uploaded_count += 1

    if uploaded_count > 0:
        db.session.commit()
        flash(f'Successfully added {uploaded_count} image(s) to gallery.', 'success')
    else:
        flash('Please select one or more image files or enter an image URL.', 'error')

    return redirect(url_for('admin_edit_product', product_id=product.id))


@app.route('/admin/products/<int:product_id>/variants/<int:variant_id>/restock', methods=['POST'])
@admin_required
def admin_restock_variant(product_id, variant_id):
    """Restocks inventory for a specific variant and logs an audit trail."""
    product = Product.query.get_or_404(product_id)
    variant = ProductVariant.query.filter_by(id=variant_id, product_id=product.id).first_or_404()

    quantity_added = request.form.get('quantity_added', type=int)
    notes = (request.form.get('notes') or '').strip()

    if not quantity_added or quantity_added <= 0:
        flash('Please specify a positive restock quantity to add.', 'error')
        return redirect(url_for('admin_edit_product', product_id=product.id))

    curr_user = get_current_user()
    prev_stock = variant.stock_quantity
    new_stock = prev_stock + quantity_added
    variant.stock_quantity = new_stock

    log = InventoryRestockLog(
        product_id=product.id,
        variant_id=variant.id,
        admin_id=curr_user.id if curr_user else None,
        admin_name=curr_user.name if curr_user else 'Administrator',
        previous_stock=prev_stock,
        quantity_added=quantity_added,
        new_stock=new_stock,
        notes=notes or None
    )
    db.session.add(log)
    db.session.commit()

    flash(f'Restocked variant {variant.size} / {variant.colour} (+{quantity_added} units). Updated stock: {new_stock}.', 'success')
    return redirect(url_for('admin_edit_product', product_id=product.id))


@app.route('/admin/products/<int:product_id>/images/delete/<int:image_id>', methods=['POST'])
@admin_required
def admin_delete_image(product_id, image_id):
    img = ProductImage.query.filter_by(id=image_id, product_id=product_id).first_or_404()
    try:
        storage_service.delete_image(img.image_url)
    except Exception as e:
        app.logger.warning(f"Could not delete physical image: {e}")
    db.session.delete(img)
    db.session.commit()
    flash('Image removed from gallery.', 'success')
    return redirect(url_for('admin_edit_product', product_id=product_id))


@app.route('/admin/categories')
@admin_required
def admin_categories():
    categories = Category.query.order_by(Category.display_order).all()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/categories/add', methods=['POST'])
@admin_required
def admin_add_category():
    name = (request.form.get('name') or '').strip()
    parent_id = request.form.get('parent_id', type=int) or None
    description = (request.form.get('description') or '').strip()
    image_url = (request.form.get('image_url') or '').strip()
    is_visible_on_storefront = bool(request.form.get('is_visible_on_storefront'))

    if not name:
        flash('Category name is required.', 'error')
        return redirect(url_for('admin_categories'))

    base_slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower()).strip('-')
    slug = base_slug
    c = 1
    while Category.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{c}"
        c += 1

    cat = Category(
        name=name,
        slug=slug,
        parent_id=parent_id,
        description=description,
        image_url=image_url,
        is_active=True,
        is_visible_on_storefront=is_visible_on_storefront
    )
    db.session.add(cat)
    db.session.commit()
    status_str = "visible on storefront" if is_visible_on_storefront else "hidden from storefront (admin only)"
    flash(f'Category "{name}" created ({status_str}).', 'success')
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/edit/<int:category_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == 'POST':
        category.name = (request.form.get('name') or category.name).strip()
        category.description = (request.form.get('description') or '').strip()
        category.image_url = (request.form.get('image_url') or '').strip()
        parent_id = request.form.get('parent_id', type=int) or None
        if parent_id != category.id:
            category.parent_id = parent_id
        category.is_visible_on_storefront = bool(request.form.get('is_visible_on_storefront'))
        category.is_active = bool(request.form.get('is_active'))
        category.display_order = request.form.get('display_order', 0, type=int)

        db.session.commit()
        flash(f'Category "{category.name}" updated successfully.', 'success')
        return redirect(url_for('admin_categories'))

    top_categories = Category.query.filter(Category.parent_id == None, Category.id != category.id).all()
    return render_template('admin/edit_category.html', category=category, top_categories=top_categories)


@app.route('/admin/categories/<int:category_id>/toggle-visibility', methods=['POST'])
@admin_required
def admin_toggle_category_visibility(category_id):
    cat = Category.query.get_or_404(category_id)
    cat.is_visible_on_storefront = not cat.is_visible_on_storefront
    # Keep child subcategories in sync if top-level toggled
    for sub in cat.subcategories:
        sub.is_visible_on_storefront = cat.is_visible_on_storefront
    db.session.commit()
    status = "visible on customer storefront" if cat.is_visible_on_storefront else "hidden from customer storefront"
    flash(f'Category "{cat.name}" is now {status}.', 'success')
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/delete/<int:category_id>', methods=['POST'])
@admin_required
def admin_delete_category(category_id):
    cat = Category.query.get_or_404(category_id)
    name = cat.name
    # Check if active products belong to this category
    has_products = Product.query.filter(
        (Product.category_id == cat.id) | (Product.subcategory_id == cat.id)
    ).count() > 0
    if has_products:
        flash(f'Cannot delete category "{name}" because products are currently assigned to it. Reassign or delete products first.', 'error')
        return redirect(url_for('admin_categories'))

    for sub in cat.subcategories:
        sub.parent_id = None
    db.session.delete(cat)
    db.session.commit()
    flash(f'Category "{name}" has been deleted.', 'success')
    return redirect(url_for('admin_categories'))


@app.route('/admin/orders')
@admin_required
def admin_orders():
    """Admin order list with search and status filtering."""
    status_filter = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    q = Order.query
    if status_filter:
        q = q.filter(Order.order_status == status_filter)
    if search:
        q = q.filter(
            or_(
                Order.order_number.ilike(f'%{search}%'),
                Order.full_name.ilike(f'%{search}%'),
                Order.email.ilike(f'%{search}%')
            )
        )

    paginated = q.order_by(desc(Order.created_at)).paginate(page=page, per_page=15, error_out=False)

    return render_template(
        'admin/orders.html',
        orders=paginated.items,
        pagination=paginated,
        status_filter=status_filter,
        search=search
    )


@app.route('/admin/orders/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    payment_txn = PaymentTransaction.query.filter_by(order_id=order.id).first()
    return render_template('admin/order_detail.html', order=order, payment_txn=payment_txn)


@app.route('/admin/orders/<int:order_id>/update-status', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get('order_status', '')
    courier_name = (request.form.get('courier_name') or '').strip()
    tracking = (request.form.get('tracking_number') or '').strip()
    tracking_url = (request.form.get('tracking_url') or '').strip()
    notes = (request.form.get('notes') or '').strip()
    notify_customer = request.form.get('notify_customer', 'true').lower() in ['true', 'on', '1', 'yes']
    submitted_pay_status = (request.form.get('payment_status') or '').strip().lower()

    valid_statuses = ['Pending', 'Confirmed', 'Processing', 'Shipped', 'Out for Delivery', 'Delivered', 'Cancelled', 'Returned']
    if status not in valid_statuses:
        flash('Invalid order status.', 'error')
        return redirect(url_for('admin_order_detail', order_id=order.id))

    old_status = order.order_status
    order.order_status = status
    if courier_name:
        order.courier_name = courier_name
    if tracking:
        order.tracking_number = tracking
    if tracking_url:
        order.tracking_url = tracking_url

    if status == 'Shipped' and not order.shipped_at:
        order.shipped_at = datetime.utcnow()
    elif status == 'Delivered' and not order.delivered_at:
        order.delivered_at = datetime.utcnow()

    # Validate payment status transitions securely based on payment method
    if submitted_pay_status:
        if order.payment_method == 'cod':
            if submitted_pay_status in ['pending', 'collected', 'paid', 'failed']:
                order.payment_status = 'collected' if submitted_pay_status in ['collected', 'paid'] else submitted_pay_status
            else:
                flash(f'Invalid payment status "{submitted_pay_status}" for COD order.', 'error')
        elif order.payment_method == 'razorpay':
            if submitted_pay_status in ['paid', 'collected'] and order.payment_status != 'paid':
                flash('Online Razorpay payments cannot be manually marked as Paid without verified gateway confirmation.', 'error')
                return redirect(url_for('admin_order_detail', order_id=order.id))
            elif submitted_pay_status in ['refunded', 'failed', 'pending']:
                order.payment_status = submitted_pay_status

    # Create immutable audit log entry
    log_entry = OrderStatusLog(
        order_id=order.id,
        old_status=old_status,
        new_status=status,
        notes=notes,
        courier_name=order.courier_name,
        tracking_number=order.tracking_number,
        tracking_url=order.tracking_url,
        changed_by='admin',
        customer_notified=False
    )
    db.session.add(log_entry)
    db.session.commit()

    # Send status update notification email if requested and status has changed
    if notify_customer and (status != order.last_notified_status or status != old_status):
        try:
            result = send_order_status_email(
                order,
                new_status=status,
                courier_name=order.courier_name,
                tracking_number=order.tracking_number,
                tracking_url=order.tracking_url,
                notes=notes
            )
            if result:
                order.last_notified_status = status
                log_entry.customer_notified = True
                log_entry.notified_at = datetime.utcnow()
                log_entry.notification_error = None
            else:
                log_entry.customer_notified = False
                log_entry.notification_error = result.message if hasattr(result, 'message') else "Failed to send status update email."
            db.session.commit()
        except Exception as exc:
            app.logger.warning('Failed to dispatch status email to %s: %s', order.email, exc)
            log_entry.customer_notified = False
            log_entry.notification_error = str(exc)
            db.session.commit()

    flash(f'Order #{order.order_number} updated to {status}.', 'success')
    return redirect(url_for('admin_order_detail', order_id=order.id))


@app.route('/admin/orders/<int:order_id>/resend-notification/<int:log_id>', methods=['POST'])
@admin_required
def admin_resend_order_notification(order_id, log_id):
    """Retries customer email dispatch for a specific order status log entry."""
    order = Order.query.get_or_404(order_id)
    log_entry = OrderStatusLog.query.filter_by(id=log_id, order_id=order.id).first_or_404()

    force = (request.args.get('force', '').lower() in ('1', 'true')) or (request.form.get('force', '').lower() in ('1', 'true'))
    if log_entry.customer_notified and not force:
        flash("Customer has already been notified for this status event. To resend anyway, explicit confirmation is required.", "warning")
        return redirect(url_for('admin_order_detail', order_id=order.id))

    try:
        result = send_order_status_email(
            order,
            new_status=log_entry.status,
            courier_name=log_entry.courier_name or order.courier_name,
            tracking_number=log_entry.tracking_number or order.tracking_number,
            tracking_url=log_entry.tracking_url or order.tracking_url,
            notes=log_entry.notes
        )
        if result:
            log_entry.customer_notified = True
            log_entry.notified_at = datetime.utcnow()
            log_entry.notification_error = None
            order.last_notified_status = log_entry.status
            db.session.commit()
            flash(f"Status notification successfully resent to {order.email}.", "success")
        else:
            log_entry.customer_notified = False
            log_entry.notification_error = result.message if hasattr(result, 'message') else "Resend failed."
            db.session.commit()
            flash(f"Failed to resend notification: {log_entry.notification_error}", "error")
    except Exception as exc:
        app.logger.warning("Error resending notification for Order #%s: %s", order.order_number, exc)
        log_entry.customer_notified = False
        log_entry.notification_error = str(exc)
        db.session.commit()
        flash(f"Error resending notification: {exc}", "error")

    return redirect(url_for('admin_order_detail', order_id=order.id))


@app.route('/admin/orders/<int:order_id>/mark-cod-collected', methods=['POST'])
@admin_required
def admin_mark_cod_collected(order_id):
    """Allows authorized admin to record payment collection for Cash on Delivery orders."""
    order = Order.query.get_or_404(order_id)
    if order.payment_method != 'cod':
        flash('Only Cash on Delivery orders can be marked as collected.', 'error')
        return redirect(url_for('admin_order_detail', order_id=order.id))

    order.payment_status = 'collected'
    db.session.commit()
    flash(f'Payment for COD Order #{order.order_number} marked as Collected.', 'success')
    return redirect(url_for('admin_order_detail', order_id=order.id))


@app.route('/admin/payments')
@admin_required
def admin_payments():
    """Admin view for inspecting PaymentTransaction gateway records."""
    status_filter = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    q = PaymentTransaction.query
    if status_filter:
        q = q.filter(PaymentTransaction.status == status_filter)
    if search:
        q = q.filter(
            or_(
                PaymentTransaction.gateway_order_id.ilike(f'%{search}%'),
                PaymentTransaction.gateway_payment_id.ilike(f'%{search}%')
            )
        )

    paginated = q.order_by(desc(PaymentTransaction.id)).paginate(page=page, per_page=15, error_out=False)

    return render_template(
        'admin/payments.html',
        transactions=paginated.items,
        pagination=paginated,
        status_filter=status_filter,
        search=search
    )


@app.route('/admin/customers')
@admin_required
def admin_customers():
    """Customer accounts directory. Strictly excludes administrator accounts."""
    customers = User.query.filter_by(is_admin=False).order_by(desc(User.id)).all()
    return render_template('admin/customers.html', customers=customers)


@app.route('/admin/customers/<int:customer_id>')
@admin_required
def admin_customer_detail(customer_id):
    customer = User.query.get_or_404(customer_id)
    if customer.is_admin:
        flash('Administrator accounts cannot be viewed or manipulated in Customer Directory.', 'error')
        return redirect(url_for('admin_customers'))
    orders = Order.query.filter_by(customer_id=customer.id).order_by(desc(Order.created_at)).all()
    return render_template('admin/customer_detail.html', customer=customer, orders=orders)


# ------------------------------------------------------------------------------
# REVIEWS & CONTACT MESSAGES MANAGEMENT
# ------------------------------------------------------------------------------

@app.route('/admin/reviews')
@admin_required
def admin_reviews():
    """Admin view for moderating customer product reviews."""
    reviews = ProductReview.query.order_by(desc(ProductReview.created_at)).all()
    return render_template('admin/reviews.html', reviews=reviews)


@app.route('/admin/reviews/<int:review_id>/approve', methods=['POST'])
@admin_required
def admin_approve_review(review_id):
    rev = ProductReview.query.get_or_404(review_id)
    rev.is_approved = True
    db.session.commit()
    flash(f'Review #{rev.id} has been approved.', 'success')
    return redirect(url_for('admin_reviews'))


@app.route('/admin/reviews/<int:review_id>/disapprove', methods=['POST'])
@admin_required
def admin_disapprove_review(review_id):
    rev = ProductReview.query.get_or_404(review_id)
    rev.is_approved = False
    db.session.commit()
    flash(f'Review #{rev.id} marked as pending moderation.', 'info')
    return redirect(url_for('admin_reviews'))


@app.route('/admin/reviews/<int:review_id>/delete', methods=['POST'])
@admin_required
def admin_delete_review(review_id):
    rev = ProductReview.query.get_or_404(review_id)
    db.session.delete(rev)
    db.session.commit()
    flash(f'Review #{review_id} permanently deleted.', 'success')
    return redirect(url_for('admin_reviews'))


@app.route('/admin/messages')
@admin_required
def admin_contact_messages():
    """Admin view for inspecting submitted customer inquiries."""
    messages = ContactMessage.query.order_by(desc(ContactMessage.created_at)).all()
    return render_template('admin/messages.html', messages=messages)


@app.route('/admin/messages/<int:message_id>/mark_read', methods=['POST'])
@admin_required
def admin_mark_message_read(message_id):
    msg = ContactMessage.query.get_or_404(message_id)
    msg.is_read = True
    msg.status = 'read'
    db.session.commit()
    flash(f'Message #{msg.id} marked as read.', 'success')
    return redirect(url_for('admin_contact_messages'))


@app.route('/admin/messages/<int:message_id>/mark_unread', methods=['POST'])
@admin_required
def admin_mark_message_unread(message_id):
    msg = ContactMessage.query.get_or_404(message_id)
    msg.is_read = False
    msg.status = 'unread'
    db.session.commit()
    flash(f'Message #{msg.id} marked as unread.', 'success')
    return redirect(url_for('admin_contact_messages'))


@app.route('/admin/messages/<int:message_id>/delete', methods=['POST'])
@admin_required
def admin_delete_message(message_id):
    msg = ContactMessage.query.get_or_404(message_id)
    db.session.delete(msg)
    db.session.commit()
    flash(f'Message #{message_id} permanently deleted.', 'success')
    return redirect(url_for('admin_contact_messages'))


@app.route('/admin/customers/<int:customer_id>/delete', methods=['POST'])
@admin_required
def admin_delete_customer(customer_id):
    """
    Safely delete a customer account while preserving financial transaction
    records and historical orders with customer_id=NULL.
    Strictly forbids deleting administrator accounts.
    """
    customer = User.query.get_or_404(customer_id)
    if customer.is_admin:
        flash('Administrator accounts cannot be deleted through Customer Management.', 'error')
        return redirect(url_for('admin_customers'))

    customer_name = customer.name
    customer_email = customer.email
    try:
        # Disassociate customer_id from audit logs to preserve financial history
        PaymentTransaction.query.filter_by(customer_id=customer.id).update({'customer_id': None})
        Order.query.filter_by(customer_id=customer.id).update({'customer_id': None})

        # Explicitly clean up user-specific personal data
        Address.query.filter_by(user_id=customer.id).delete()
        Wishlist.query.filter_by(user_id=customer.id).delete()
        ProductReview.query.filter_by(user_id=customer.id).delete()

        db.session.delete(customer)
        db.session.commit()
        flash(f'Customer account "{customer_name}" ({customer_email}) was deleted successfully. Historical orders and payment records have been preserved.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete customer: {str(e)}', 'error')

    return redirect(url_for('admin_customers'))


@app.route('/admin/coupons')
@admin_required
def admin_coupons():
    coupons = Coupon.query.order_by(desc(Coupon.id)).all()
    return render_template('admin/coupons.html', coupons=coupons)


@app.route('/admin/coupons/add', methods=['POST'])
@admin_required
def admin_add_coupon():
    code = (request.form.get('code') or '').strip().upper()
    discount_type = request.form.get('discount_type', 'percentage')
    discount_value = request.form.get('discount_value', type=float)
    min_purchase = request.form.get('min_purchase', 0.0, type=float)
    max_discount = request.form.get('max_discount', type=float) or None
    usage_limit = request.form.get('usage_limit', 100, type=int)

    if not code or not discount_value:
        flash('Coupon code and discount value are required.', 'error')
        return redirect(url_for('admin_coupons'))

    if Coupon.query.filter_by(code=code).first():
        flash('Coupon code already exists.', 'error')
        return redirect(url_for('admin_coupons'))

    coupon = Coupon(
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        min_purchase=min_purchase,
        max_discount=max_discount,
        usage_limit=usage_limit
    )
    db.session.add(coupon)
    db.session.commit()
    flash(f'Coupon "{code}" created.', 'success')
    return redirect(url_for('admin_coupons'))


@app.route('/admin/coupons/toggle/<int:coupon_id>', methods=['POST'])
@admin_required
def admin_toggle_coupon(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    coupon.is_active = not coupon.is_active
    db.session.commit()
    flash(f'Coupon "{coupon.code}" {"activated" if coupon.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin_coupons'))


@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        for key in ['store_name', 'tagline', 'contact_email', 'contact_phone', 'address', 'delivery_charge', 'free_delivery_threshold', 'cod_enabled', 'return_policy']:
            val = request.form.get(key)
            if val is not None:
                StoreSetting.set(key, val)
        flash('Store settings saved successfully.', 'success')
        return redirect(url_for('admin_settings'))

    settings = {
        'store_name': StoreSetting.get('store_name', 'COSTUME STORE'),
        'tagline': StoreSetting.get('tagline', 'Premium Costumes, Cosplay & Theatrical Sales'),
        'contact_email': StoreSetting.get('contact_email', 'support@costumestore.com'),
        'contact_phone': StoreSetting.get('contact_phone', '+91 98765 43210'),
        'address': StoreSetting.get('address', '45 Heritage Boulevard, Fashion District, Bengaluru'),
        'delivery_charge': StoreSetting.get('delivery_charge', '99.0'),
        'free_delivery_threshold': StoreSetting.get('free_delivery_threshold', '1499.0'),
        'cod_enabled': StoreSetting.get('cod_enabled', 'true'),
        'return_policy': StoreSetting.get('return_policy', '')
    }
    return render_template('admin/settings.html', settings=settings)


# ------------------------------------------------------------------------------
# API ENDPOINT FOR LIVE DYNAMIC VARIANT STOCK & PRICE
# ------------------------------------------------------------------------------

@app.route('/api/variant-stock')
def api_variant_stock():
    product_id = request.args.get('product_id', type=int)
    size = request.args.get('size', '').strip()
    colour = request.args.get('colour', '').strip()

    if not product_id:
        return jsonify({'error': 'Missing product_id'}), 400

    q = ProductVariant.query.filter_by(product_id=product_id, is_active=True)
    if size:
        q = q.filter_by(size=size)
    if colour:
        q = q.filter_by(colour=colour)

    variant = q.first()
    if not variant:
        return jsonify({'in_stock': False, 'stock_quantity': 0, 'variant_id': None})

    return jsonify({
        'in_stock': variant.stock_quantity > 0,
        'stock_quantity': variant.stock_quantity,
        'variant_id': variant.id,
        'sku': variant.sku,
        'effective_price': variant.effective_price,
        'formatted_price': f"₹{variant.effective_price:.2f}"
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Vercel, load-balancers, and monitoring."""
    status = {
        'status': 'healthy',
        'service': 'COSTUME STORE E-Commerce',
        'timestamp': datetime.utcnow().isoformat()
    }
    db_ok = True
    try:
        db.session.execute(text('SELECT 1'))
        status['database'] = 'connected'
    except Exception as e:
        db_ok = False
        status['database'] = f'error: {str(e)}'
        status['status'] = 'unhealthy'
    
    code = 200 if db_ok else 503
    return jsonify(status), code


# ------------------------------------------------------------------------------
# DATABASE INITIALIZATION AT STARTUP
# ------------------------------------------------------------------------------

def init_application_database(application):
    """
    Initialize database schema and sync administrator safely.
    In production, catalogue import is explicitly decoupled and executed via scripts/import_catalogue.py.
    In development mode, schema tables and approved catalogue are seeded if empty.
    """
    is_prod = (
        os.environ.get('FLASK_ENV', '').lower() == 'production' or
        bool(os.environ.get('VERCEL')) or
        bool(os.environ.get('RENDER'))
    )
    with application.app_context():
        if not is_prod:
            db.create_all()
            try:
                inspector = inspect(db.engine)
                cols = [c['name'] for c in inspector.get_columns('category')]
                if 'is_visible_on_storefront' not in cols:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE category ADD COLUMN is_visible_on_storefront BOOLEAN NOT NULL DEFAULT 1"))
                        conn.commit()
            except Exception:
                pass

            try:
                active_count = Product.query.filter_by(is_active=True).count()
                if active_count < 26:
                    from seed_costume_data import seed_database
                    seed_database()
            except Exception as e:
                application.logger.warning(f"Development catalogue initialization note: {e}")
        else:
            # Production mode: create schema if explicitly enabled or run via migration
            from config import parse_bool
            if parse_bool(os.environ.get('AUTO_CREATE_TABLES'), default=False):
                try:
                    db.create_all()
                except Exception as e:
                    application.logger.warning(f"Production AUTO_CREATE_TABLES notice: {e}")

        # Synchronize primary administrator from environment if configured
        try:
            sync_admin_from_env(application)
        except Exception as e:
            application.logger.warning(f"Admin synchronization from environment warning: {e}")

init_application_database(app)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
