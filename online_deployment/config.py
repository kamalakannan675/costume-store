import os
import re
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)
DEFAULT_SQLITE_DB = os.path.join(INSTANCE_DIR, 'costume_store.db').replace('\\', '/')
DEFAULT_SQLITE_URI = f"sqlite:///{DEFAULT_SQLITE_DB}"


def parse_bool(val, default=False):
    """Safely parse boolean configuration flags from environment variables or dictionaries."""
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


def normalize_database_url(url: str) -> str:
    """
    Normalizes PostgreSQL database URLs for SQLAlchemy 2.x and psycopg2.
    Supports Neon PostgreSQL, standard PostgreSQL, and cloud connection poolers.
    Replaces deprecated 'postgres://' with 'postgresql://'.
    Ensures remote PostgreSQL URLs have sslmode=require if not present.
    """
    if not url:
        return ""
    cleaned = url.strip()
    if cleaned.startswith('postgres://'):
        cleaned = cleaned.replace('postgres://', 'postgresql://', 1)

    # For Neon and remote PostgreSQL, ensure sslmode=require is present if not local SQLite or localhost
    if cleaned.startswith(('postgresql://', 'postgres://')):
        if 'localhost' not in cleaned and '127.0.0.1' not in cleaned and 'sqlite' not in cleaned:
            if 'sslmode=' not in cleaned:
                delimiter = '&' if '?' in cleaned else '?'
                cleaned = f"{cleaned}{delimiter}sslmode=require"
    return cleaned


class Config:
    """Base application configuration for Costume Store online deployment (Vercel + Neon)."""
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', '').strip()
    OTP_SECRET_KEY = os.environ.get('OTP_SECRET_KEY', '').strip()

    # Database Configuration (Neon PostgreSQL in production or local SQLite fallback)
    raw_db_url = os.environ.get('DATABASE_URL')
    if raw_db_url and raw_db_url.strip():
        db_url = normalize_database_url(raw_db_url)
        if db_url.startswith('sqlite:///'):
            path_part = db_url[len('sqlite:///'):]
            if not os.path.isabs(path_part) and not path_part.startswith('/'):
                abs_db_path = os.path.abspath(os.path.join(BASE_DIR, path_part)).replace('\\', '/')
                db_url = f"sqlite:///{abs_db_path}"
    else:
        db_url = DEFAULT_SQLITE_URI

    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Serverless-Safe Connection Pooling (Optimized for Neon PostgreSQL & Vercel Functions)
    is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
    if is_serverless:
        # Ephemeral container settings: small pool, pre-ping active, recycle to avoid stale PgBouncer handles
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 2,
            'max_overflow': 3,
            'pool_timeout': 30,
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
        }

    # Uploads & File Management
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'products')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

    # Persistent Storage Configuration (S3 / Cloudflare R2 / Wasabi / Supabase Storage)
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'local').strip().lower()
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '').strip()
    S3_REGION_NAME = os.environ.get('S3_REGION_NAME', 'us-east-1').strip()
    S3_ACCESS_KEY_ID = os.environ.get('S3_ACCESS_KEY_ID', '').strip()
    S3_SECRET_ACCESS_KEY = os.environ.get('S3_SECRET_ACCESS_KEY', '').strip()
    S3_ENDPOINT_URL = os.environ.get('S3_ENDPOINT_URL', '').strip() or None
    S3_PUBLIC_URL_PREFIX = os.environ.get('S3_PUBLIC_URL_PREFIX', '').strip() or None

    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False

    # Razorpay Payment Gateway Credentials (Strictly Test Mode by default)
    RAZORPAY_MODE = os.environ.get('RAZORPAY_MODE', 'test').strip().lower()
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '').strip()
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '').strip()
    RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '').strip()

    # SMTP / Mail Server Configuration
    MAIL_SERVER = (os.environ.get('MAIL_SERVER') or os.environ.get('SMTP_HOST') or 'smtp.gmail.com').strip()
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or os.environ.get('SMTP_PORT') or '587')
    MAIL_USE_TLS = parse_bool(os.environ.get('MAIL_USE_TLS') if os.environ.get('MAIL_USE_TLS') is not None else os.environ.get('SMTP_USE_TLS'), default=True)
    MAIL_USE_SSL = parse_bool(os.environ.get('MAIL_USE_SSL') if os.environ.get('MAIL_USE_SSL') is not None else os.environ.get('SMTP_USE_SSL'), default=False)
    MAIL_USERNAME = (os.environ.get('MAIL_USERNAME') or os.environ.get('SMTP_USERNAME') or '').strip()
    MAIL_PASSWORD = (os.environ.get('MAIL_PASSWORD') or os.environ.get('SMTP_PASSWORD') or '').strip()
    MAIL_DEFAULT_SENDER = (os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('SMTP_FROM') or os.environ.get('MAIL_USERNAME') or '').strip()
    MAIL_ENABLED = parse_bool(os.environ.get('MAIL_ENABLED'), default=False)
    MAIL_ADMIN_NOTIFICATION_EMAIL = (os.environ.get('MAIL_ADMIN_NOTIFICATION_EMAIL') or os.environ.get('SMTP_ADMIN_EMAIL') or '').strip()

    # Backward compatibility aliases
    SMTP_HOST = MAIL_SERVER
    SMTP_PORT = MAIL_PORT
    SMTP_USERNAME = MAIL_USERNAME
    SMTP_PASSWORD = MAIL_PASSWORD
    SMTP_FROM = MAIL_DEFAULT_SENDER
    SMTP_ADMIN_EMAIL = MAIL_ADMIN_NOTIFICATION_EMAIL
    SMTP_USE_SSL = MAIL_USE_SSL
    SMTP_USE_TLS = MAIL_USE_TLS

    # Administrator Environment Configuration
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', '').strip().lower()
    ADMIN_NAME = (os.environ.get('ADMIN_NAME') or 'Store Administrator').strip()
    ADMIN_PASSWORD = (os.environ.get('ADMIN_PASSWORD') or os.environ.get('ADMIN_PASSWROD') or '').strip()


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # Enforce HTTPS on Vercel
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Production secrets: NO default fallback to insecure development keys
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')

    raw_db_url = os.environ.get('DATABASE_URL', '').strip()
    SQLALCHEMY_DATABASE_URI = normalize_database_url(raw_db_url)

    @classmethod
    def validate(cls, database_url=None, secret_key=None):
        """Validate production configuration and fail fast if critical credentials or database are missing."""
        errors = []

        # 1. Secret Key validation
        secret = (secret_key if secret_key is not None else os.environ.get('FLASK_SECRET_KEY', '')).strip()
        if not secret:
            errors.append(
                "FLASK_SECRET_KEY environment variable is missing. A cryptographically secure random key (>= 32 chars) is required."
            )
        elif len(secret) < 32:
            errors.append(
                f"FLASK_SECRET_KEY is too short ({len(secret)} characters). Cryptographically secure production keys must be at least 32 characters."
            )
        elif any(bad in secret.lower() for bad in ['dev', 'placeholder', 'change', 'secret', 'default', 'test', 'replace']):
            errors.append(
                "FLASK_SECRET_KEY contains insecure default/placeholder words. Generate a true high-entropy cryptographic secret."
            )
        elif len(set(secret)) < 10:
            errors.append(
                "FLASK_SECRET_KEY has insufficient character variety (low entropy). Use a cryptographically generated string."
            )

        # 2. PostgreSQL Database URL validation (Neon PostgreSQL required)
        db_url = (database_url if database_url is not None else os.environ.get('DATABASE_URL', '')).strip()
        if not db_url:
            errors.append(
                "DATABASE_URL is missing in production. A PostgreSQL connection URL is required "
                "(e.g. from Neon: postgresql://user:pass@ep-xyz.region.aws.neon.tech/neondb?sslmode=require)."
            )
        else:
            scheme = db_url.split('://')[0].lower() if '://' in db_url else ''
            if scheme in {'sqlite', 'sqlite3'}:
                errors.append(
                    "DATABASE_URL points to SQLite. Production mode strictly prohibits SQLite fallback to guarantee data persistence; "
                    "PostgreSQL (such as Neon) is required."
                )
            elif scheme not in {'postgresql', 'postgres', 'postgresql+psycopg2'}:
                errors.append(
                    f"DATABASE_URL uses unsupported database scheme '{scheme}'. Only PostgreSQL is supported in production "
                    "(e.g. from Neon: postgresql://username:password@ep-xyz.region.aws.neon.tech/neondb?sslmode=require)."
                )

        if errors:
            formatted_errors = "\n  - " + "\n  - ".join(errors)
            raise RuntimeError(
                f"\n[CRITICAL PRODUCTION SECURITY ERROR]\n"
                f"Production startup failed due to configuration validation errors:{formatted_errors}\n"
                f"Please configure strong environment variables in your Vercel Project Settings."
            )


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'testing-ephemeral-secret-key-32-chars-fixed!'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


def get_config():
    """Select appropriate configuration class based on environment."""
    env = os.environ.get('FLASK_ENV', '').lower()
    is_cloud_prod = bool(os.environ.get('VERCEL') or os.environ.get('RENDER'))
    if env == 'production' or is_cloud_prod:
        ProductionConfig.validate()
        return ProductionConfig
    elif env == 'testing':
        return TestingConfig

    # Development mode validation
    secret = (os.environ.get('FLASK_SECRET_KEY') or '').strip()
    if not secret:
        raise RuntimeError(
            "FLASK_SECRET_KEY environment variable is required. "
            "Please configure a cryptographically secure 32-byte secret in your local .env file."
        )
    predictable_defaults = {
        'dev-costume-store-secret-key-change-in-prod',
        'dev-costume-store-local-secret-key-32-chars-minimum',
        'secret', 'changeme', 'admin123', 'password'
    }
    if secret.lower() in predictable_defaults or len(secret) < 32:
        raise RuntimeError(
            "FLASK_SECRET_KEY is insecure, predictable, or shorter than 32 characters. "
            "Please generate a secure cryptographic secret (e.g. secrets.token_hex(32))."
        )

    return DevelopmentConfig
