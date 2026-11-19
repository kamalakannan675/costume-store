"""
COSTUME STORE — Media & Persistent File Storage Service
Provides a production-grade storage abstraction supporting:
1. Local Filesystem Storage (default for development: static/uploads/products)
2. S3-Compatible Cloud Storage (AWS S3, Cloudflare R2, MinIO, Wasabi, Supabase) for persistent cloud deployments.
"""

import os
import re
import secrets
from datetime import datetime
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_MIME_TYPES = {
    'image/png',
    'image/jpeg',
    'image/pjpeg',
    'image/webp',
    'image/gif'
}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB


class StorageBackend:
    """Base interface for file storage backends."""
    def save(self, file_storage, filename: str) -> str:
        raise NotImplementedError

    def delete(self, file_url: str) -> bool:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""
    def __init__(self, upload_folder: str):
        self.upload_folder = os.path.abspath(upload_folder)
        is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
        if not is_serverless:
            try:
                os.makedirs(self.upload_folder, exist_ok=True)
            except OSError:
                pass

    def save(self, file_storage, filename: str) -> str:
        safe_name = secure_filename(filename)
        dest_path = os.path.join(self.upload_folder, safe_name)
        # Prevent path traversal
        if not os.path.abspath(dest_path).startswith(self.upload_folder):
            raise ValueError("Potential path traversal detected.")
        if hasattr(file_storage, 'save'):
            file_storage.save(dest_path)
        else:
            if hasattr(file_storage, 'seek'):
                file_storage.seek(0)
            with open(dest_path, 'wb') as f_out:
                f_out.write(file_storage.read())
        return f"/static/uploads/products/{safe_name}"

    def delete(self, file_url: str) -> bool:
        if not file_url or not file_url.startswith('/static/uploads/products/'):
            return False
        filename = secure_filename(os.path.basename(file_url))
        target_path = os.path.join(self.upload_folder, filename)
        if os.path.exists(target_path) and os.path.isfile(target_path):
            try:
                os.remove(target_path)
                return True
            except OSError:
                return False
        return False


class ReadOnlyDisabledStorageBackend(StorageBackend):
    """Safe fallback backend when external storage is unconfigured in a serverless read-only environment."""
    def save(self, file_storage, filename: str) -> str:
        raise RuntimeError(
            "Product image upload failed: External persistent storage (S3/R2) is not configured in this serverless deployment. "
            "Please configure S3_BUCKET_NAME, S3_ACCESS_KEY_ID, and S3_SECRET_ACCESS_KEY in your Vercel Project Settings."
        )

    def delete(self, file_url: str) -> bool:
        return False


class S3StorageBackend(StorageBackend):
    """Amazon S3 and S3-compatible cloud object storage backend."""
    def __init__(self, bucket_name: str, access_key: str, secret_key: str,
                 region: str = 'us-east-1', endpoint_url: str = None,
                 public_url_prefix: str = None):
        self.bucket_name = bucket_name
        self.region = region
        self.endpoint_url = endpoint_url
        self.public_url_prefix = public_url_prefix.rstrip('/') if public_url_prefix else None

        try:
            import boto3
            self.s3_client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                endpoint_url=self.endpoint_url
            )
        except ImportError:
            raise RuntimeError("boto3 package is required for S3 storage backend. Please install boto3.")

    def save(self, file_storage, filename: str) -> str:
        safe_name = secure_filename(filename)
        s3_key = f"products/{safe_name}"
        
        # Read content type
        content_type = getattr(file_storage, 'content_type', 'application/octet-stream')
        
        # Reset stream position if needed
        if hasattr(file_storage, 'seek'):
            file_storage.seek(0)

        self.s3_client.upload_fileobj(
            file_storage,
            self.bucket_name,
            s3_key,
            ExtraArgs={'ContentType': content_type}
        )

        if self.public_url_prefix:
            return f"{self.public_url_prefix}/{s3_key}"
        elif self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{s3_key}"
        else:
            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"

    def delete(self, file_url: str) -> bool:
        if not file_url:
            return False
        s3_key = f"products/{os.path.basename(file_url)}"
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except Exception:
            return False


class StorageService:
    """High-level storage service facade managing image validation and persistence."""
    def __init__(self, app=None):
        self.backend = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
        backend_type = app.config.get('STORAGE_BACKEND', 'local').lower()
        if backend_type == 's3':
            bucket = app.config.get('S3_BUCKET_NAME')
            key = app.config.get('S3_ACCESS_KEY_ID')
            secret = app.config.get('S3_SECRET_ACCESS_KEY')
            if not bucket or not key or not secret:
                if is_serverless:
                    app.logger.warning(
                        "STORAGE_BACKEND is 's3' but S3 credentials are not configured in Vercel. "
                        "Admin image uploads will fail safely until S3/R2 credentials are set."
                    )
                    self.backend = ReadOnlyDisabledStorageBackend()
                else:
                    app.logger.warning(
                        "STORAGE_BACKEND is set to 's3' but credentials are incomplete. Falling back to local storage."
                    )
                    self.backend = LocalStorageBackend(app.config['UPLOAD_FOLDER'])
            else:
                self.backend = S3StorageBackend(
                    bucket_name=bucket,
                    access_key=key,
                    secret_key=secret,
                    region=app.config.get('S3_REGION_NAME', 'us-east-1'),
                    endpoint_url=app.config.get('S3_ENDPOINT_URL'),
                    public_url_prefix=app.config.get('S3_PUBLIC_URL_PREFIX')
                )
        else:
            if is_serverless:
                app.logger.warning(
                    "STORAGE_BACKEND is 'local' in a serverless environment with a read-only filesystem. "
                    "Admin image uploads will fail safely until S3/R2 is configured."
                )
                self.backend = ReadOnlyDisabledStorageBackend()
            else:
                self.backend = LocalStorageBackend(app.config['UPLOAD_FOLDER'])

    def validate_image_file(self, file_storage) -> tuple[bool, str]:
        """Validate filename, extension, and content type."""
        if not file_storage or not file_storage.filename:
            return False, "No file selected."
        
        filename = file_storage.filename
        if '.' not in filename:
            return False, "File must have a valid image extension."
        
        ext = filename.rsplit('.', 1)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"File format '.{ext}' is not supported. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        
        content_type = getattr(file_storage, 'content_type', '')
        if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
            return False, f"Invalid MIME content type: '{content_type}'."
        
        # Check size if available
        if hasattr(file_storage, 'content_length') and file_storage.content_length:
            if file_storage.content_length > MAX_FILE_SIZE:
                return False, f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE // (1024*1024)}MB."

        return True, ""

    def generate_unique_filename(self, original_filename: str, prefix: str = "prod") -> str:
        """Generate a tamper-proof collision-resistant filename."""
        safe_orig = secure_filename(original_filename)
        ext = safe_orig.rsplit('.', 1)[1].lower() if '.' in safe_orig else 'jpg'
        clean_stem = re.sub(r'[^a-zA-Z0-9_]', '_', safe_orig.rsplit('.', 1)[0])[:30]
        timestamp = int(datetime.utcnow().timestamp())
        random_token = secrets.token_hex(4)
        return f"{prefix}_{timestamp}_{random_token}_{clean_stem}.{ext}"

    def save_image(self, file_storage, prefix: str = "prod") -> str:
        """Validate and persist an uploaded image."""
        is_valid, err_msg = self.validate_image_file(file_storage)
        if not is_valid:
            raise ValueError(err_msg)
        
        filename = self.generate_unique_filename(file_storage.filename, prefix=prefix)
        return self.backend.save(file_storage, filename)

    def delete_image(self, image_url: str) -> bool:
        """Safely delete an uploaded image from storage backend."""
        if not image_url:
            return False
        # Do NOT delete bundled static product images (/static/images/products/...)
        if image_url.startswith('/static/images/'):
            return False
        return self.backend.delete(image_url)


storage_service = StorageService()
