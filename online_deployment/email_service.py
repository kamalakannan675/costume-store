"""
COSTUME STORE — Reusable SMTP Email & Transactional Notification Service

Handles all customer and store communications:
  1. Order confirmation and status updates (Placed, Confirmed, Shipped, Out for Delivery, Delivered, Cancelled).
  2. Shipment tracking notifications with courier details and direct tracking URLs.
  3. Customer account deletion OTP dispatch with strict security headers.
  4. Password reset and email verification workflows.
  5. Admin new-order notification dispatch.

Safety Invariants:
  - Credentials remain strictly in .env / config; never logged or exposed.
  - Failures in email dispatch NEVER roll back orders, payments, or customer records.
  - Multi-part MIME (HTML + text fallback) ensures 100% email client compatibility.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from flask import current_app

logger = logging.getLogger('costume_store.email')


class EmailResult:
    """
    Structured outcome of an email dispatch attempt.
    Supports boolean truthiness evaluation, 2-tuple unpacking (success, message),
    and attribute access (.success, .message).
    """
    def __init__(self, success: bool, message: str = ""):
        self.success = bool(success)
        self.message = str(message or "")

    def __bool__(self):
        return self.success

    def __iter__(self):
        yield self.success
        yield self.message

    def __getitem__(self, idx):
        return (self.success, self.message)[idx]

    def __eq__(self, other):
        if isinstance(other, bool):
            return self.success is other
        if isinstance(other, tuple) and len(other) == 2:
            return (self.success, self.message) == other
        if isinstance(other, EmailResult):
            return (self.success, self.message) == (other.success, other.message)
        return False

    def __repr__(self):
        return f"EmailResult(success={self.success}, message='{self.message}')"


def _parse_bool_setting(val, default=False):
    """Safely parse boolean configuration values."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ('true', '1', 'yes', 't', 'y', 'enabled'):
        return True
    if s in ('false', '0', 'no', 'f', 'n', 'disabled'):
        return False
    return default


def _get_setting_bool(cfg, keys, default=False):
    for k in keys:
        if k in cfg and cfg[k] is not None and (not isinstance(cfg[k], str) or cfg[k].strip() != ''):
            return _parse_bool_setting(cfg[k], default)
    for k in keys:
        if k in os.environ and os.environ[k] is not None and os.environ[k].strip() != '':
            return _parse_bool_setting(os.environ[k], default)
    return default


def _get_setting_str(cfg, keys, default=''):
    for k in keys:
        val = cfg.get(k)
        if val is not None and str(val).strip() != '':
            return str(val).strip()
    for k in keys:
        val = os.environ.get(k)
        if val is not None and str(val).strip() != '':
            return str(val).strip()
    return default


def get_mail_config():
    """Retrieve validated SMTP configuration from Flask current_app or environment."""
    cfg = current_app.config if current_app else {}
    server = _get_setting_str(cfg, ['MAIL_SERVER', 'SMTP_HOST'], default='smtp.gmail.com')
    raw_port = _get_setting_str(cfg, ['MAIL_PORT', 'SMTP_PORT'], default='587')
    try:
        port = int(raw_port)
    except (ValueError, TypeError):
        port = 587

    use_tls = _get_setting_bool(cfg, ['MAIL_USE_TLS', 'SMTP_USE_TLS'], default=True)
    use_ssl = _get_setting_bool(cfg, ['MAIL_USE_SSL', 'SMTP_USE_SSL'], default=False)
    username = _get_setting_str(cfg, ['MAIL_USERNAME', 'SMTP_USERNAME'], default='')
    password = _get_setting_str(cfg, ['MAIL_PASSWORD', 'SMTP_PASSWORD'], default='')
    sender = _get_setting_str(cfg, ['MAIL_DEFAULT_SENDER', 'SMTP_FROM', 'MAIL_USERNAME'], default='no-reply@costumestore.local')
    enabled = _get_setting_bool(cfg, ['MAIL_ENABLED'], default=False)
    admin_alert_email = _get_setting_str(cfg, ['MAIL_ADMIN_NOTIFICATION_EMAIL', 'SMTP_ADMIN_EMAIL'], default='')

    config_error = None
    if use_tls and use_ssl:
        config_error = "Conflicting SMTP security configuration: Cannot enable both MAIL_USE_TLS and MAIL_USE_SSL simultaneously."
        logger.warning(config_error)

    return {
        'server': server,
        'port': port,
        'use_tls': use_tls,
        'use_ssl': use_ssl,
        'username': username,
        'password': password,
        'sender': sender,
        'enabled': enabled,
        'admin_alert_email': admin_alert_email,
        'config_error': config_error
    }


def is_mail_configured():
    """Check if SMTP email dispatch is fully enabled and configured with non-empty credentials."""
    cfg = get_mail_config()
    if cfg.get('config_error'):
        return False
    return bool(cfg['enabled'] and cfg['server'] and cfg['username'] and cfg['password'] and cfg['sender'])


def send_email(to_email, subject, html_content, text_content=None):
    """
    Core SMTP email dispatcher.
    Returns EmailResult(success: bool, message: str).
    Guarantees no sensitive credentials appear in return messages or log outputs.
    """
    to_email = (to_email or '').strip()
    if not to_email:
        return EmailResult(False, "Recipient email address is missing.")

    cfg = get_mail_config()
    if cfg.get('config_error'):
        return EmailResult(False, cfg['config_error'])

    if not cfg['enabled']:
        logger.info("Mail service is disabled (MAIL_ENABLED=False); skipped email to %s: '%s'", to_email, subject)
        return EmailResult(False, "Mail service is disabled (MAIL_ENABLED=False).")

    if not (cfg['server'] and cfg['username'] and cfg['password']):
        logger.info("SMTP credentials incomplete; skipped email to %s: '%s'", to_email, subject)
        return EmailResult(False, "SMTP configuration incomplete (missing server, username, or password).")

    if not text_content:
        # Create a simple plain-text fallback from HTML
        import re
        text_content = re.sub(r'<[^>]+>', ' ', html_content)
        text_content = re.sub(r'\s+', ' ', text_content).strip()

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"COSTUME STORE <{cfg['sender']}>"
        msg['To'] = to_email
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid(domain='costumestore.local')

        # Attach text then HTML (email clients prefer last part)
        part_text = MIMEText(text_content, 'plain', 'utf-8')
        part_html = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(part_text)
        msg.attach(part_html)

        if cfg['use_ssl']:
            with smtplib.SMTP_SSL(cfg['server'], cfg['port'], timeout=15) as smtp:
                smtp.login(cfg['username'], cfg['password'])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg['server'], cfg['port'], timeout=15) as smtp:
                if cfg['use_tls']:
                    smtp.starttls()
                smtp.login(cfg['username'], cfg['password'])
                smtp.send_message(msg)

        logger.info("Email successfully sent to %s with subject: '%s'", to_email, subject)
        return EmailResult(True, f"Email sent successfully to {to_email}.")

    except smtplib.SMTPAuthenticationError:
        logger.warning("SMTP Authentication Failed for user %s. Please verify your App Password.", cfg['username'])
        return EmailResult(False, "SMTP authentication failed. Check username and app password.")
    except Exception as exc:
        # Sanitize exception message to ensure no secrets or password tokens are leaked
        err_msg = str(exc)
        if cfg['password'] and cfg['password'] in err_msg:
            err_msg = err_msg.replace(cfg['password'], '[REDACTED]')
        logger.warning("SMTP delivery error to %s: %s", to_email, err_msg)
        return EmailResult(False, f"SMTP delivery error: {err_msg}")


# ------------------------------------------------------------------------------
# BRANDED HTML TEMPLATE WRAPPER
# ------------------------------------------------------------------------------

def _render_email_base(title, content_html, preheader=""):
    """Wrap content in a luxury responsive email template matching COSTUME STORE branding."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ margin:0; padding:0; background:#F4EFE6; font-family:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; color:#222222; -webkit-font-smoothing:antialiased; }}
    table {{ border-collapse:collapse; }}
    .container {{ max-width:600px; margin:30px auto; background:#FFFFFF; border-radius:12px; overflow:hidden; border:1px solid #E5DFD5; box-shadow:0 4px 20px rgba(0,0,0,0.06); }}
    .header {{ background:#5B1427; padding:32px 24px; text-align:center; }}
    .brand-title {{ font-family:'Playfair Display',Georgia,serif; font-size:24px; color:#FFFFFF; margin:0; letter-spacing:1px; }}
    .brand-subtitle {{ font-size:11px; color:#D4AF37; letter-spacing:2px; text-transform:uppercase; margin-top:6px; }}
    .body {{ padding:36px 32px; font-size:15px; line-height:1.6; color:#333333; }}
    .footer {{ background:#FAF7F2; padding:24px; text-align:center; font-size:12px; color:#777777; border-top:1px solid #EFEAE1; }}
    .badge {{ display:inline-block; padding:6px 14px; border-radius:20px; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; }}
    .badge-primary {{ background:#FBE8EC; color:#5B1427; }}
    .badge-success {{ background:#E6F4EA; color:#137333; }}
    .badge-info {{ background:#E8F0FE; color:#1A73E8; }}
    .badge-warning {{ background:#FEF7E0; color:#B06000; }}
    .btn {{ display:inline-block; padding:12px 28px; background:#5B1427; color:#FFFFFF !important; text-decoration:none; border-radius:6px; font-weight:700; font-size:14px; margin:20px 0 10px 0; }}
    .order-table {{ width:100%; margin:20px 0; border:1px solid #EFEAE1; border-radius:8px; overflow:hidden; }}
    .order-table th {{ background:#F9F6F0; padding:10px 14px; font-size:12px; text-transform:uppercase; text-align:left; color:#666; }}
    .order-table td {{ padding:12px 14px; border-top:1px solid #EFEAE1; font-size:14px; }}
    .otp-box {{ background:#FBF6EE; border:2px dashed #C5A059; border-radius:8px; padding:20px; text-align:center; margin:24px 0; }}
    .otp-code {{ font-family:monospace; font-size:32px; font-weight:700; letter-spacing:8px; color:#5B1427; }}
  </style>
</head>
<body>
  <div style="display:none;font-size:1px;color:#333333;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
    {preheader}
  </div>
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F4EFE6;padding:20px 10px;">
    <tr>
      <td align="center">
        <div class="container">
          <div class="header">
            <h1 class="brand-title">COSTUME STORE</h1>
            <div class="brand-subtitle">Authentic Indian Traditional Attire</div>
          </div>
          <div class="body">
            {content_html}
          </div>
          <div class="footer">
            <p style="margin:0 0 8px 0;font-weight:600;color:#5B1427;">COSTUME STORE &bull; Handcrafted Heritage Collections</p>
            <p style="margin:0 0 6px 0;">Express Dispatch Across India &bull; 100% Secure Checkout</p>
            <p style="margin:0;font-size:11px;color:#999999;">This is a transactional communication regarding your customer account or order.</p>
          </div>
        </div>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ------------------------------------------------------------------------------
# 1. ORDER NOTIFICATIONS
# ------------------------------------------------------------------------------

def _build_order_items_table_html(order):
    """Builds HTML table listing order items, quantities, and prices."""
    rows = []
    for item in order.items:
        variant_desc = f"{item.size} / {item.colour}" if (item.size or item.colour) else ""
        rows.append(f"""
        <tr>
          <td>
            <strong>{item.product_name}</strong>
            <br><span style="font-size:12px;color:#666;">{variant_desc}</span>
          </td>
          <td align="center">x{item.quantity}</td>
          <td align="right">₹{item.total_price:,.2f}</td>
        </tr>
        """)
    return f"""
    <table class="order-table" cellpadding="0" cellspacing="0">
      <thead>
        <tr>
          <th>Item Description</th>
          <th style="text-align:center;">Qty</th>
          <th style="text-align:right;">Total</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
      <tfoot>
        <tr>
          <td colspan="2" align="right" style="padding-top:14px;color:#666;">Subtotal:</td>
          <td align="right" style="padding-top:14px;font-weight:600;">₹{order.subtotal:,.2f}</td>
        </tr>
        {f'<tr><td colspan="2" align="right" style="color:#137333;">Coupon Discount ({order.coupon_code}):</td><td align="right" style="color:#137333;">-₹{order.discount_amount:,.2f}</td></tr>' if order.discount_amount else ''}
        <tr>
          <td colspan="2" align="right" style="color:#666;">Delivery Fee:</td>
          <td align="right" style="font-weight:600;">{'FREE' if order.delivery_fee == 0 else f'₹{order.delivery_fee:,.2f}'}</td>
        </tr>
        <tr style="font-size:16px;">
          <td colspan="2" align="right" style="font-weight:700;color:#5B1427;border-top:2px solid #5B1427;">Payable Total:</td>
          <td align="right" style="font-weight:700;color:#5B1427;border-top:2px solid #5B1427;">₹{order.total_amount:,.2f}</td>
        </tr>
      </tfoot>
    </table>
    """


def send_order_placed_email(order):
    """Notify customer that their order has been placed successfully."""
    subject = f"Order Placed #{order.order_number} — COSTUME STORE"
    content = f"""
    <h2 style="color:#5B1427;margin-top:0;">Thank you for your order!</h2>
    <p>Dear <strong>{order.full_name}</strong>,</p>
    <p>Your order <strong>#{order.order_number}</strong> has been placed successfully. We are preparing your authentic traditional garments for express dispatch.</p>
    
    <div style="background:#F9F6F0;padding:14px 18px;border-radius:6px;margin:20px 0;">
      <div><strong>Order Number:</strong> #{order.order_number}</div>
      <div><strong>Order Date:</strong> {order.created_at.strftime('%d %B %Y, %I:%M %p')}</div>
      <div><strong>Payment Method:</strong> {'Cash on Delivery (COD)' if order.payment_method == 'cod' else 'Online Payment (Razorpay)'}</div>
      <div><strong>Payment Status:</strong> <span class="badge badge-{'success' if order.payment_status == 'paid' else 'warning'}">{order.payment_status.upper()}</span></div>
    </div>

    <h3 style="color:#5B1427;font-size:16px;margin-bottom:8px;">Items in Your Order</h3>
    {_build_order_items_table_html(order)}

    <h3 style="color:#5B1427;font-size:16px;margin:20px 0 8px 0;">Delivery Address</h3>
    <p style="background:#FAF8F5;padding:12px;border-radius:6px;margin:0;line-height:1.5;">
      {order.shipping_address}<br>
      {order.city}, {order.state} - {order.pincode}<br>
      Phone: +91 {order.phone}
    </p>
    """
    html = _render_email_base(subject, content, preheader=f"Order #{order.order_number} placed successfully.")
    return send_email(order.email, subject, html)


def send_payment_received_email(order, payment_id=None, transaction_id=None):
    """Notify customer that payment has been verified and received."""
    active_payment_id = payment_id or transaction_id
    subject = f"Payment Confirmed for Order #{order.order_number} — COSTUME STORE"
    content = f"""
    <h2 style="color:#137333;margin-top:0;"><i style="font-size:24px;">✓</i> Payment Received Successfully</h2>
    <p>Dear <strong>{order.full_name}</strong>,</p>
    <p>We have successfully received and verified your payment of <strong>₹{order.total_amount:,.2f}</strong> for Order <strong>#{order.order_number}</strong>.</p>
    
    <div style="background:#F0F9F4;border:1px solid #C6E7D2;padding:16px;border-radius:6px;margin:20px 0;">
      <div><strong>Order Ref:</strong> #{order.order_number}</div>
      <div><strong>Amount Paid:</strong> ₹{order.total_amount:,.2f}</div>
      <div><strong>Payment Gateway:</strong> Razorpay Secure 256-bit</div>
      {f'<div><strong>Transaction ID:</strong> {active_payment_id}</div>' if active_payment_id else ''}
      <div><strong>Status:</strong> <span class="badge badge-success">PAID</span></div>
    </div>

    <p>Your garments are currently queued for express inspection and protective packing.</p>
    """
    html = _render_email_base(subject, content, preheader=f"Payment verified for Order #{order.order_number}.")
    return send_email(order.email, subject, html)


def send_order_status_email(order, new_status, courier_name=None, tracking_number=None, tracking_url=None, notes=None):
    """
    Notify customer whenever their order status transitions (e.g. Shipped, Delivered).
    Includes courier partner, tracking number, and direct tracking links for shipped orders.
    """
    courier = courier_name or order.courier_name
    tracking = tracking_number or order.tracking_number
    track_url = tracking_url or order.tracking_url

    status_badge_class = 'primary'
    if new_status in ('Delivered', 'Confirmed'):
        status_badge_class = 'success'
    elif new_status in ('Cancelled', 'Returned'):
        status_badge_class = 'warning'
    elif new_status in ('Shipped', 'Out for Delivery'):
        status_badge_class = 'info'

    subject = f"Order #{order.order_number} Status Update: {new_status} — COSTUME STORE"
    
    tracking_section = ""
    if new_status in ('Shipped', 'Out for Delivery') or tracking:
        tracking_section = f"""
        <div style="background:#F0F4FA;border:1px solid #D2E0F5;border-radius:8px;padding:18px;margin:20px 0;">
          <h4 style="margin:0 0 10px 0;color:#1A73E8;font-size:15px;">📦 Shipment & Tracking Information</h4>
          <div><strong>Courier Partner:</strong> {courier or 'Express Surface Logistics'}</div>
          <div><strong>Tracking AWB / Number:</strong> <span style="font-family:monospace;font-weight:700;">{tracking or 'Pending Courier Scan'}</span></div>
          {f'<div style="margin-top:12px;"><a href="{track_url}" target="_blank" class="btn" style="display:inline-block;padding:10px 20px;font-size:13px;">Track Package Online &rarr;</a></div>' if track_url else ''}
        </div>
        """

    content = f"""
    <h2 style="color:#5B1427;margin-top:0;">Order Status Update</h2>
    <p>Dear <strong>{order.full_name}</strong>,</p>
    <p>The status of your order <strong>#{order.order_number}</strong> has been updated to:</p>
    
    <div style="margin:16px 0;">
      <span class="badge badge-{status_badge_class}" style="font-size:16px;padding:8px 20px;">{new_status}</span>
    </div>

    {f'<p style="color:#555;font-style:italic;background:#FAF8F5;padding:10px;border-left:3px solid #5B1427;">"{notes}"</p>' if notes else ''}

    {tracking_section}

    <h3 style="color:#5B1427;font-size:16px;margin:24px 0 8px 0;">Order Summary</h3>
    {_build_order_items_table_html(order)}
    """
    html = _render_email_base(subject, content, preheader=f"Order #{order.order_number} is now {new_status}.")
    return send_email(order.email, subject, html)


def send_admin_new_order_alert(order):
    """Send store administrators an instant notification when a new order is received."""
    cfg = get_mail_config()
    admin_email = cfg.get('admin_alert_email') or os.environ.get('SMTP_ADMIN_EMAIL')
    if not admin_email:
        return EmailResult(False, "No admin notification email configured.")

    subject = f"[ADMIN ORDER ALERT] New Order #{order.order_number} Received (₹{order.total_amount:,.2f})"
    content = f"""
    <h2 style="color:#5B1427;margin-top:0;">New Customer Order Received</h2>
    <div style="background:#F9F6F0;padding:16px;border-radius:6px;margin-bottom:20px;">
      <div><strong>Order Number:</strong> #{order.order_number}</div>
      <div><strong>Customer Name:</strong> {order.full_name} ({order.email})</div>
      <div><strong>Customer Phone:</strong> +91 {order.phone}</div>
      <div><strong>Payment Method:</strong> {order.payment_method.upper()}</div>
      <div><strong>Payment Status:</strong> {order.payment_status.upper()}</div>
      <div><strong>Total Amount:</strong> ₹{order.total_amount:,.2f}</div>
    </div>
    {_build_order_items_table_html(order)}
    """
    html = _render_email_base(subject, content, preheader=f"New order #{order.order_number} placed by {order.full_name}.")
    return send_email(admin_email, subject, html)


# ------------------------------------------------------------------------------
# 2. ACCOUNT SECURITY & OTP EMAILS
# ------------------------------------------------------------------------------

def send_account_deletion_otp(to_email, user_name, otp_code, expires_minutes=5):
    """
    Send single-use account deletion verification OTP.
    Displays clear warnings about irreversible data deletion and statutory order retention.
    """
    subject = f"Account Deletion Verification Code: {otp_code} — COSTUME STORE"
    content = f"""
    <h2 style="color:#B91C1C;margin-top:0;">Account Deletion Request</h2>
    <p>Dear <strong>{user_name}</strong>,</p>
    <p>We received an explicit request to permanently delete your customer account for <strong>COSTUME STORE</strong>.</p>
    
    <div class="otp-box">
      <div style="font-size:12px;color:#777;margin-bottom:6px;text-transform:uppercase;letter-spacing:1px;">Your Single-Use Verification Code</div>
      <div class="otp-code">{otp_code}</div>
      <div style="font-size:12px;color:#B91C1C;margin-top:8px;">Valid for exactly {expires_minutes} minutes &bull; Single-use only</div>
    </div>

    <div style="background:#FEE2E2;border:1px solid #FCA5A5;padding:14px;border-radius:6px;font-size:13px;color:#991B1B;line-height:1.5;">
      <strong>Important Information:</strong>
      <ul style="margin:6px 0 0 0;padding-left:20px;">
        <li>Confirming this code will permanently remove your login credentials, saved addresses, wishlists, and reviews.</li>
        <li>Historical order and payment audit logs are retained anonymously for statutory commercial compliance (with personal association removed).</li>
        <li>If you did not request this deletion, please sign in and change your password immediately.</li>
      </ul>
    </div>
    """
    html = _render_email_base(subject, content, preheader=f"Your account deletion code is {otp_code}.")
    return send_email(to_email, subject, html)


def send_password_reset_email(to_email, user_name, reset_url, expires_minutes=15):
    """Send time-limited password recovery link."""
    subject = "Password Reset Request — COSTUME STORE"
    content = f"""
    <h2 style="color:#5B1427;margin-top:0;">Password Reset Request</h2>
    <p>Dear <strong>{user_name}</strong>,</p>
    <p>We received a request to reset the password for your COSTUME STORE customer account.</p>
    
    <div style="text-align:center;margin:30px 0;">
      <a href="{reset_url}" class="btn" style="font-size:15px;padding:14px 32px;">Reset Your Password &rarr;</a>
      <div style="font-size:12px;color:#777;margin-top:10px;">This link is valid for {expires_minutes} minutes.</div>
    </div>

    <p style="font-size:13px;color:#666;">
      If you did not initiate this request, you can safely ignore this email; your existing password will remain unchanged.
    </p>
    <p style="font-size:12px;color:#999;word-break:break-all;">
      If the button does not work, copy and paste this URL into your browser:<br>{reset_url}
    </p>
    """
    html = _render_email_base(subject, content, preheader="Reset your COSTUME STORE account password.")
    return send_email(to_email, subject, html)


def send_registration_welcome_email(user):
    """Send a welcoming onboarding email to newly registered customers."""
    subject = f"Welcome to COSTUME STORE, {user.name}!"
    content = f"""
    <h2 style="color:#5B1427;margin-top:0;">Welcome to the Heritage Collection!</h2>
    <p>Dear <strong>{user.name}</strong>,</p>
    <p>Thank you for creating an account with <strong>COSTUME STORE</strong>, India's leading destination for pure handcrafted silk sarees, regal groom sherwanis, festive lehengas, and authentic dance wear.</p>
    
    <div style="background:#F9F6F0;border-left:4px solid #C5A059;padding:16px;border-radius:4px;margin:24px 0;">
      <h4 style="margin:0 0 6px 0;color:#5B1427;">Your Account Benefits:</h4>
      <ul style="margin:0;padding-left:20px;font-size:14px;color:#444;">
        <li>Saved delivery address auto-populates during checkout.</li>
        <li>Live order tracking and milestone notifications.</li>
        <li>Save your favorite costumes to your private wishlist.</li>
        <li>Enjoy 10% off your first purchase with coupon code: <strong style="color:#5B1427;">WELCOME10</strong></li>
      </ul>
    </div>

    <p>We hope you enjoy celebrating the splendour of Indian traditional attire with us.</p>
    """
    html = _render_email_base(subject, content, preheader="Welcome to COSTUME STORE! Your account is ready.")
    return send_email(user.email, subject, html)
