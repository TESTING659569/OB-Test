"""Shared S3/R2 client factory for maintenance scripts."""

from __future__ import annotations

import os
from typing import Literal

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

StorageBackend = Literal["aws", "r2"]


def create_storage_client(backend: StorageBackend = "aws"):
    """
    Create a boto3 S3 client for AWS S3 or Cloudflare R2.

    AWS uses AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION.
    R2 uses CF_R2_ACCESS_KEY_ID, CF_R2_SECRET_ACCESS_KEY, CF_R2_ENDPOINT_URL.
    """
    if backend == "r2":
        access_key = os.environ.get("CF_R2_ACCESS_KEY_ID")
        secret_key = os.environ.get("CF_R2_SECRET_ACCESS_KEY")
        endpoint_url = os.environ.get("CF_R2_ENDPOINT_URL")
        if not all([access_key, secret_key, endpoint_url]):
            raise NoCredentialsError(
                "Set CF_R2_ACCESS_KEY_ID, CF_R2_SECRET_ACCESS_KEY, and CF_R2_ENDPOINT_URL."
            )
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    if access_key and secret_key:
        return boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
    return boto3.client("s3", region_name=region)


def get_bucket_name(backend: StorageBackend = "aws") -> str:
    if backend == "r2":
        return os.environ.get("CF_R2_BUCKET_NAME", "data-collection-dl")
    return os.environ.get("AWS_S3_BUCKET_NAME", "data-collection-dl")


def verify_bucket_access(client, bucket: str) -> bool:
    try:
        client.head_bucket(Bucket=bucket)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        print(f"ERROR: Cannot access bucket '{bucket}' ({code})")
        return False
    except Exception as exc:
        print(f"ERROR: Unexpected error accessing bucket '{bucket}': {exc}")
        return False
