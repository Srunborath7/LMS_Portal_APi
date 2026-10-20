from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import UploadFile

from app.core.exceptions import BadRequest, ServiceUnavailable


load_dotenv()
logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 5 * 1024 * 1024
IMAGE_FORMATS = (
    (b"\x89PNG\r\n\x1a\n", ".png", "image/png"),
    (b"\xff\xd8\xff", ".jpg", "image/jpeg"),
)


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def get_upload_dir() -> Path:
    configured = _env("UPLOAD_DIR")
    return Path(configured).expanduser() if configured else Path(__file__).resolve().parents[2] / "uploads"


def _storage_backend() -> str:
    configured = (_env("IMAGE_STORAGE_BACKEND") or "").lower()
    if configured:
        if configured not in {"local", "supabase"}:
            raise RuntimeError("IMAGE_STORAGE_BACKEND must be 'local' or 'supabase'.")
        return configured
    # Use durable object storage automatically when its credentials are present.
    required = (
        "SUPABASE_S3_ENDPOINT", "SUPABASE_S3_REGION", "SUPABASE_S3_ACCESS_KEY_ID",
        "SUPABASE_S3_SECRET_ACCESS_KEY", "SUPABASE_STORAGE_BUCKET",
    )
    return "supabase" if all(_env(key) for key in required) else "local"


def _s3_settings() -> tuple[str, str, str, str, str]:
    names = (
        "SUPABASE_S3_ENDPOINT", "SUPABASE_S3_REGION", "SUPABASE_S3_ACCESS_KEY_ID",
        "SUPABASE_S3_SECRET_ACCESS_KEY", "SUPABASE_STORAGE_BUCKET",
    )
    values = [_env(name) for name in names]
    missing = [name for name, value in zip(names, values) if value is None]
    if missing:
        raise RuntimeError("Image storage configuration is missing: " + ", ".join(missing))
    return tuple(values)  # type: ignore[return-value]


def _get_s3_client():
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RuntimeError("Install boto3 to use Supabase image storage: pip install boto3") from exc

    endpoint, region, access_key, secret_key, _ = _s3_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _public_object_url(key: str) -> str:
    endpoint, _, _, _, bucket = _s3_settings()
    host = urlsplit(endpoint).hostname or ""
    suffix = ".storage.supabase.co"
    if not host.endswith(suffix):
        raise RuntimeError("SUPABASE_S3_ENDPOINT must use the Supabase Storage hostname.")
    project_ref = host[: -len(suffix)]
    return (
        f"https://{project_ref}.supabase.co/storage/v1/object/public/"
        f"{quote(bucket, safe='')}/{quote(key, safe='/')}"
    )


def _image_format(content: bytes) -> tuple[bytes, str, str] | None:
    found = next((item for item in IMAGE_FORMATS if content.startswith(item[0])), None)
    if found:
        return found
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return b"RIFF", ".webp", "image/webp"
    return None


async def save_image(upload: UploadFile, folder: str) -> str:
    """Validate and store an image, returning its public URL."""
    if folder not in {"students", "teachers"}:
        raise ValueError("Unsupported image folder.")
    content = await upload.read(MAX_IMAGE_SIZE + 1)
    if not content:
        raise BadRequest("The uploaded image is empty.")
    if len(content) > MAX_IMAGE_SIZE:
        raise BadRequest("Image must be 5 MB or smaller.")

    image_format = _image_format(content)
    if image_format is None:
        raise BadRequest("Upload a PNG, JPEG, or WebP image.")
    _, extension, content_type = image_format
    key = f"{folder}/{uuid4().hex}{extension}"

    try:
        if _storage_backend() == "supabase":
            _, _, _, _, bucket = _s3_settings()
            client = _get_s3_client()
            await asyncio.to_thread(
                client.put_object,
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
            )
            return _public_object_url(key)

        directory = get_upload_dir() / folder
        await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
        destination = directory / Path(key).name
        await asyncio.to_thread(destination.write_bytes, content)
        return f"/uploads/{folder}/{destination.name}"
    except BadRequest:
        raise
    except Exception as exc:
        logger.exception("Unable to store uploaded image")
        raise ServiceUnavailable("Image storage is currently unavailable.") from exc


async def remove_image(image_url: str | None) -> None:
    """Remove an image previously stored by this service; ignore unrelated URLs."""
    if not image_url:
        return

    try:
        parsed = urlsplit(image_url)
        if _storage_backend() == "supabase":
            endpoint, _, _, _, bucket = _s3_settings()
            storage_host = urlsplit(endpoint).hostname or ""
            project_ref = storage_host.removesuffix(".storage.supabase.co")
            expected_host = f"{project_ref}.supabase.co"
            bucket_prefix = f"/storage/v1/object/public/{quote(bucket, safe='')}/"
            if parsed.scheme != "https" or parsed.hostname != expected_host or not parsed.path.startswith(bucket_prefix):
                return
            key = unquote(parsed.path[len(bucket_prefix):])
            if not key.startswith(("students/", "teachers/")):
                return
            _, _, _, _, bucket = _s3_settings()
            await asyncio.to_thread(_get_s3_client().delete_object, Bucket=bucket, Key=key)
            return

        parts = Path(parsed.path).parts
        if len(parts) != 4 or parts[1] != "uploads" or parts[2] not in {"students", "teachers"}:
            return
        filename = parts[3]
        if Path(filename).name != filename:
            return
        target = get_upload_dir() / parts[2] / filename
        await asyncio.to_thread(target.unlink, missing_ok=True)
    except Exception:
        # Image cleanup follows a committed database update; cleanup failures
        # should be logged without making that successful API operation fail.
        logger.exception("Unable to remove old uploaded image")
