from __future__ import annotations

import os
from api.storage.base import Storage


class R2Storage(Storage):
    """Cloudflare R2 storage provider using the S3-compatible API.

    boto3 and botocore are imported lazily inside ``__init__`` so that
    importing this module (e.g. in tests) never crashes on environments
    where boto3 is not installed or has a broken pyOpenSSL dependency.
    The crash would only occur if someone actually instantiates R2Storage,
    which the factory (artifact_store.py) only does when STORAGE_PROVIDER=r2.
    """

    def __init__(self):
        # Deferred imports so that importing the module is always safe.
        import boto3
        from botocore.config import Config
        from botocore.exceptions import ClientError  # noqa: F401 (stored below)

        # Store ClientError on the instance so all methods can reference it
        # without another module-level import.
        self._ClientError = ClientError

        self.endpoint_url = os.environ.get("R2_ENDPOINT")
        self.access_key_id = os.environ.get("R2_ACCESS_KEY_ID")
        self.secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY")
        self.bucket = os.environ.get("R2_BUCKET", "")
        self.public_base_url = os.environ.get("R2_PUBLIC_BASE_URL")

        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(signature_version="s3v4"),
        )

    def save(self, relative_path: str, content: bytes | str, content_type: str) -> None:
        body = content.encode("utf-8") if isinstance(content, str) else content
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=relative_path,
                Body=body,
                ContentType=content_type,
            )
        except self._ClientError as e:
            raise RuntimeError(f"Failed to upload {relative_path} to R2: {e}") from e

    def get(self, relative_path: str) -> bytes | None:
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=relative_path)
            return response["Body"].read()
        except self._ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise RuntimeError(f"Failed to get {relative_path} from R2: {e}") from e

    def delete(self, relative_path: str) -> None:
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=relative_path)
        except self._ClientError as e:
            raise RuntimeError(f"Failed to delete {relative_path} from R2: {e}") from e

    def exists(self, relative_path: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=relative_path)
            return True
        except self._ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return False
            raise RuntimeError(
                f"Failed to check existence of {relative_path} in R2: {e}"
            ) from e

    def url(self, relative_path: str) -> str:
        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}/{relative_path.lstrip('/')}"

        # Fall back to a presigned URL (valid for 1 hour).
        try:
            return self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": relative_path},
                ExpiresIn=3600,
            )
        except self._ClientError as e:
            raise RuntimeError(
                f"Failed to generate presigned URL for {relative_path}: {e}"
            ) from e

    # ---------------------------------------------------------------------------
    # Compatibility aliases (match the Storage protocol surface)
    # ---------------------------------------------------------------------------

    def write(self, relative_path: str, content: str, content_type: str) -> None:
        self.save(relative_path, content, content_type)

    def write_bytes(self, relative_path: str, content: bytes, content_type: str) -> None:
        self.save(relative_path, content, content_type)

    def read(self, relative_path: str) -> str | None:
        val = self.get(relative_path)
        return val.decode("utf-8") if val is not None else None

    def read_bytes(self, relative_path: str) -> bytes | None:
        return self.get(relative_path)
