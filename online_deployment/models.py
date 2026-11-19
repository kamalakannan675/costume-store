from datetime import datetime
import hmac
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ==============================================================================
# 1. USER & ADDRESS MODELS
# ==============================================================================

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    address = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_verified = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    orders = db.relationship('Order', back_populates='customer', lazy='dynamic')
    wishlist_items = db.relationship('Wishlist', back_populates='user', cascade='all, delete-orphan')
    reviews = db.relationship('ProductReview', back_populates='user', cascade='all, delete-orphan')
    addresses = db.relationship('Address', back_populates='user', cascade='all, delete-orphan')

    @property
    def default_address(self):
        if self.addresses:
            for addr in self.addresses:
                if addr.is_default:
                    return addr
            return self.addresses[0]
        return None

    def check_password(self, password):
        if not self.password or not password:
            return False
        # Reject plaintext and unsupported algorithms; strictly require valid Werkzeug password hashes
        if not self.password.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
            return False
        try:
            return check_password_hash(self.password, password)
        except Exception:
            # Malformed, corrupted, or incompatible hashes fail safely
            return False

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def __repr__(self):
        return f'<User {self.email}>'


class Address(db.Model):
    __tablename__ = 'address'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    street_address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='addresses')


# ==============================================================================
# 2. CATEGORIES, PRODUCTS & VARIANTS
# ==============================================================================

class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(300), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_visible_on_storefront = db.Column(db.Boolean, default=True, nullable=False)
    display_order = db.Column(db.Integer, default=0)

    # Self-referential relationship
    parent = db.relationship('Category', remote_side=[id], backref=db.backref('subcategories', lazy='joined', order_by='Category.display_order'))
    products = db.relationship('Product', foreign_keys='Product.category_id', back_populates='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


class Product(db.Model):
    __tablename__ = 'costume_product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=True)  # Materials, care instructions, package contents
    category_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete='RESTRICT'), nullable=False)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete='SET NULL'), nullable=True)
    brand = db.Column(db.String(100), default='Costume Store')
    base_price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float, nullable=True)  # Discounted selling price
    sku = db.Column(db.String(60), unique=True, nullable=True)
    is_featured = db.Column(db.Boolean, default=False, index=True)
    is_bestseller = db.Column(db.Boolean, default=False, index=True)
    is_trending = db.Column(db.Boolean, default=False, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    category = db.relationship('Category', foreign_keys=[category_id], back_populates='products')
    subcategory = db.relationship('Category', foreign_keys=[subcategory_id])
    images = db.relationship('ProductImage', back_populates='product', cascade='all, delete-orphan', order_by='ProductImage.display_order')
    variants = db.relationship('ProductVariant', back_populates='product', cascade='all, delete-orphan')
    reviews = db.relationship('ProductReview', back_populates='product', cascade='all, delete-orphan')

    @property
    def primary_image(self):
        for img in self.images:
            if img.is_primary:
                return img.image_url
        if self.images:
            return self.images[0].image_url
        return '/static/images/placeholder-costume.jpg'

    @property
    def effective_price(self):
        if self.discount_price and 0 < self.discount_price < self.base_price:
            return round(self.discount_price, 2)
        return round(self.base_price, 2)

    @property
    def discount_percent(self):
        if self.discount_price and self.discount_price < self.base_price:
            return int(round((self.base_price - self.discount_price) / self.base_price * 100))
        return 0

    @property
    def total_stock(self):
        if self.variants:
            return sum(v.stock_quantity for v in self.variants if v.is_active)
        return 0

    @property
    def in_stock(self):
        return self.total_stock > 0

    @property
    def available_sizes(self):
        sizes = []
        for v in self.variants:
            if v.is_active and v.stock_quantity > 0 and v.size not in sizes:
                sizes.append(v.size)
        return sizes

    @property
    def available_colours(self):
        colours = []
        seen = set()
        for v in self.variants:
            if v.is_active and v.stock_quantity > 0 and v.colour not in seen:
                seen.add(v.colour)
                colours.append({'name': v.colour, 'code': v.colour_code})
        return colours

    @property
    def average_rating(self):
        if not self.reviews:
            return None
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)

    @property
    def review_count(self):
        return len(self.reviews)

    def __repr__(self):
        return f'<Product {self.name}>'


class ProductImage(db.Model):
    __tablename__ = 'product_image'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('costume_product.id', ondelete='CASCADE'), nullable=False)
    image_url = db.Column(db.String(300), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)

    product = db.relationship('Product', back_populates='images')


class ProductVariant(db.Model):
    __tablename__ = 'product_variant'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('costume_product.id', ondelete='CASCADE'), nullable=False)
    size = db.Column(db.String(40), nullable=False)   # XS, S, M, L, XL, XXL, Free Size, 3-4Y, etc.
    colour = db.Column(db.String(50), nullable=False) # e.g. Crimson Red, Royal Blue
    colour_code = db.Column(db.String(20), default='#222222') # Hex code for swatch
    sku = db.Column(db.String(80), unique=True, nullable=True)
    stock_quantity = db.Column(db.Integer, default=0, nullable=False)
    additional_price = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)

    product = db.relationship('Product', back_populates='variants')

    @property
    def effective_price(self):
        base = self.product.effective_price if self.product else 0.0
        return round(base + (self.additional_price or 0.0), 2)

    def __repr__(self):
        return f'<Variant {self.product_id} - {self.size}/{self.colour}>'


# ==============================================================================
# 3. COUPONS & DISCOUNTS
# ==============================================================================

class Coupon(db.Model):
    __tablename__ = 'coupon'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    discount_type = db.Column(db.String(20), default='percentage') # 'percentage' or 'fixed'
    discount_value = db.Column(db.Float, nullable=False)
    min_purchase = db.Column(db.Float, default=0.0)
    max_discount = db.Column(db.Float, nullable=True) # cap for percentage discounts
    usage_limit = db.Column(db.Integer, default=100)
    times_used = db.Column(db.Integer, default=0)
    valid_from = db.Column(db.DateTime, default=datetime.utcnow)
    valid_until = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    def is_valid_for(self, subtotal):
        if not self.is_active:
            return False, 'This coupon is no longer active.'
        if self.times_used >= self.usage_limit:
            return False, 'This coupon usage limit has been reached.'
        if self.valid_until and datetime.utcnow() > self.valid_until:
            return False, 'This coupon has expired.'
        if subtotal < (self.min_purchase or 0):
            return False, f'Minimum cart subtotal of ₹{self.min_purchase:.2f} required for this coupon.'
        return True, 'Coupon valid.'

    def calculate_discount(self, subtotal):
        if self.discount_type == 'percentage':
            amt = round(subtotal * (self.discount_value / 100.0), 2)
            if self.max_discount and amt > self.max_discount:
                amt = round(self.max_discount, 2)
            return min(amt, subtotal)
        else: # fixed
            return min(round(self.discount_value, 2), subtotal)


# ==============================================================================
# 4. ORDERS & ORDER ITEMS
# ==============================================================================

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(60), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    shipping_address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    discount_amount = db.Column(db.Float, default=0.0)
    coupon_code = db.Column(db.String(50), nullable=True)
    delivery_fee = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(30), default='razorpay') # 'razorpay' or 'cod'
    payment_status = db.Column(db.String(30), default='pending') # 'pending', 'paid', 'failed', 'refunded'
    order_status = db.Column(db.String(30), default='Pending') # 'Pending', 'Confirmed', 'Processing', 'Shipped', 'Out for Delivery', 'Delivered', 'Cancelled', 'Returned'
    courier_name = db.Column(db.String(100), nullable=True)
    tracking_number = db.Column(db.String(100), nullable=True)
    tracking_url = db.Column(db.String(300), nullable=True)
    shipped_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    last_notified_status = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    customer = db.relationship('User', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Order {self.order_number} ({self.order_status})>'


class OrderStatusLog(db.Model):
    __tablename__ = 'order_status_log'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    courier_name = db.Column(db.String(100), nullable=True)
    tracking_number = db.Column(db.String(100), nullable=True)
    tracking_url = db.Column(db.String(300), nullable=True)
    customer_notified = db.Column(db.Boolean, default=False)
    notification_error = db.Column(db.Text, nullable=True)
    notified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship('Order', backref=db.backref('status_logs', lazy='dynamic', cascade='all, delete-orphan', order_by='OrderStatusLog.created_at.desc()'))

    new_status = db.synonym('status')

    def __init__(self, **kwargs):
        if 'new_status' in kwargs and 'status' not in kwargs:
            kwargs['status'] = kwargs.pop('new_status')
        self.old_status = kwargs.pop('old_status', None)
        self.changed_by = kwargs.pop('changed_by', 'system')
        super().__init__(**kwargs)


class OtpToken(db.Model):
    __tablename__ = 'otp_token'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=True)
    email = db.Column(db.String(100), nullable=False, index=True)
    token_type = db.Column(db.String(30), nullable=False) # 'account_deletion', 'password_reset', 'email_verify'
    otp_hash = db.Column(db.String(128), nullable=False)
    attempts = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)
    is_used = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('otp_tokens', cascade='all, delete-orphan'))

    token_hash = db.synonym('otp_hash')

    def __init__(self, **kwargs):
        if 'token_hash' in kwargs and 'otp_hash' not in kwargs:
            kwargs['otp_hash'] = kwargs.pop('token_hash')
        super().__init__(**kwargs)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at


class OrderItem(db.Model):
    __tablename__ = 'order_item'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('costume_product.id', ondelete='SET NULL'), nullable=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variant.id', ondelete='SET NULL'), nullable=True)
    product_name = db.Column(db.String(200), nullable=False)
    size = db.Column(db.String(40), nullable=False)
    colour = db.Column(db.String(50), nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(300), nullable=True)

    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product')
    variant = db.relationship('ProductVariant')


# ==============================================================================
# 5. WISHLIST & PRODUCT REVIEWS
# ==============================================================================

class Wishlist(db.Model):
    __tablename__ = 'wishlist'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('costume_product.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='wishlist_items')
    product = db.relationship('Product')

    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='unique_user_product_wishlist'),)


class ProductReview(db.Model):
    __tablename__ = 'product_review'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('costume_product.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1 to 5
    comment = db.Column(db.Text, nullable=True)
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', back_populates='reviews')
    user = db.relationship('User', back_populates='reviews')


# ==============================================================================
# 6. STORE SETTINGS
# ==============================================================================

class StoreSetting(db.Model):
    __tablename__ = 'store_setting'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    @classmethod
    def get(cls, key, default=None):
        setting = cls.query.filter_by(key=key).first()
        return setting.value if (setting and setting.value is not None) else default

    @classmethod
    def set(cls, key, value):
        setting = cls.query.filter_by(key=key).first()
        if not setting:
            setting = cls(key=key, value=str(value))
            db.session.add(setting)
        else:
            setting.value = str(value)
        db.session.commit()


# ==============================================================================
# 7. PAYMENT TRANSACTIONS (RAZORPAY)
# ==============================================================================

class PaymentTransaction(db.Model):
    __tablename__ = 'payment_transaction'
    id = db.Column(db.Integer, primary_key=True)
    gateway_order_id = db.Column(db.String(100), unique=True, nullable=False)
    gateway_payment_id = db.Column(db.String(100), nullable=True)
    signature = db.Column(db.String(255), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    order_type = db.Column(db.String(20), nullable=False, default='costume')
    amount_paise = db.Column(db.Integer, nullable=False)
    cart_json = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='created') # created, paid, failed, verification_failed
    order_id = db.Column(db.Integer, nullable=True)        # Linked Costume Order ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==============================================================================
# 8. CONTACT MESSAGES
# ==============================================================================

class ContactMessage(db.Model):
    __tablename__ = 'contact_message'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(30), default='new')  # 'new', 'read', 'archived'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ContactMessage {self.id} from {self.email}>'


# ==============================================================================
# 9. INVENTORY RESTOCK AUDIT LOG
# ==============================================================================

class InventoryRestockLog(db.Model):
    __tablename__ = 'inventory_restock_log'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('costume_product.id', ondelete='CASCADE'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variant.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, nullable=True)
    admin_name = db.Column(db.String(120), nullable=True)
    previous_stock = db.Column(db.Integer, nullable=False)
    quantity_added = db.Column(db.Integer, nullable=False)
    new_stock = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', backref=db.backref('restock_logs', lazy='dynamic', cascade='all, delete-orphan'))
    variant = db.relationship('ProductVariant', backref=db.backref('restock_logs', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<InventoryRestockLog Product {self.product_id} Variant {self.variant_id} (+{self.quantity_added})>'



