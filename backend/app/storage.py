from abc import ABC, abstractmethod
from pathlib import Path

import boto3
from botocore.client import Config

from .config import (
    S3_BUCKET,
    S3_ENDPOINT_URL,
    S3_KEY_PREFIX,
    S3_PRESIGNED_EXPIRES_SECONDS,
    S3_PUBLIC_BASE_URL,
    S3_REGION,
    STORAGE_BACKEND,
    UPLOAD_DIR,
)


class Storage(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes, content_type: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def url_for(self, stored_filename: str) -> str:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, upload_dir: Path):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self.upload_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def url_for(self, stored_filename: str) -> str:
        return f"/uploads/{stored_filename}"


class S3Storage(Storage):
    def __init__(self):
        if not S3_BUCKET:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        self.bucket = S3_BUCKET
        self.client = boto3.client(
            "s3",
            region_name=S3_REGION,
            endpoint_url=S3_ENDPOINT_URL,
            config=Config(signature_version="s3v4"),
        )

    def _object_key(self, key: str) -> str:
        return f"{S3_KEY_PREFIX}/{key}" if S3_KEY_PREFIX else key

    def save(self, key: str, data: bytes, content_type: str | None = None) -> str:
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._object_key(key),
            Body=data,
            **extra_args,
        )
        return key

    def url_for(self, stored_filename: str) -> str:
        key = self._object_key(stored_filename)
        if S3_PUBLIC_BASE_URL:
            return f"{S3_PUBLIC_BASE_URL.rstrip('/')}/{key}"
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=S3_PRESIGNED_EXPIRES_SECONDS,
        )


def get_storage() -> Storage:
    if STORAGE_BACKEND == "s3":
        return S3Storage()
    return LocalStorage(UPLOAD_DIR)


storage = get_storage()
