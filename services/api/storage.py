import hashlib
import hmac
import os
import time
from pathlib import PurePosixPath
from services.api.config import DATA, SIGNING_KEY, STORAGE, MAX_BYTES


def signature(key: str, expires: int, operation: str):
    return hmac.new(SIGNING_KEY.encode(), f"{operation}:{key}:{expires}".encode(), hashlib.sha256).hexdigest()


def valid_signature(key, expires, operation, token):
    return time.time() < expires and hmac.compare_digest(signature(key, expires, operation), token)


class Store:
    def __init__(self):
        self.root = DATA / "objects"
        self.root.mkdir(parents=True, exist_ok=True)
        self.s3 = None
        if STORAGE == "s3":
            import boto3
            from botocore.config import Config

            config = Config(signature_version="s3v4", s3={"addressing_style": "path"})
            self.s3 = boto3.client("s3", endpoint_url=os.getenv("S3_ENDPOINT"), config=config)
            self.public_s3 = boto3.client(
                "s3", endpoint_url=os.getenv("S3_PUBLIC_ENDPOINT", os.getenv("S3_ENDPOINT")), config=config
            )
            self.bucket = os.environ["S3_BUCKET"]

    def path(self, key):
        parts = PurePosixPath(key).parts
        if (
            not parts
            or any(p in ("..", ".") for p in parts)
            or "\\" in key
            or ":" in key
            or key.startswith("/")
        ):
            raise ValueError("Invalid object key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Invalid object key")
        return path

    def put(self, key, data, mime="application/octet-stream"):
        if self.s3:
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=mime)
        else:
            path = self.path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)

    def get(self, key):
        if self.s3:
            obj = self.s3.get_object(Bucket=self.bucket, Key=key)
            if obj["ContentLength"] > MAX_BYTES:
                raise ValueError("Object exceeds size limit")
            with obj["Body"] as body:
                return body.read(MAX_BYTES + 1)
        path = self.path(key)
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Object exceeds size limit")
        return path.read_bytes()

    def upload_url(self, key, mime):
        if self.s3:
            return self.public_s3.generate_presigned_url(
                "put_object", Params={"Bucket": self.bucket, "Key": key, "ContentType": mime}, ExpiresIn=300
            )
        expires = int(time.time()) + 300
        return f"/v1/objects/{key}?expires={expires}&token={signature(key, expires, 'put')}"

    def image_url(self, key):
        if self.s3:
            return self.public_s3.generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=900
            )
        expires = int(time.time()) + 900
        return f"/v1/objects/{key}?expires={expires}&token={signature(key, expires, 'get')}"


store = Store()
