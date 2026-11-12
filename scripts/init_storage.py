"""Create the local demo bucket without depending on the retired MinIO mc image."""

import os
import time
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

client = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"], config=Config(signature_version="s3v4"))
bucket = os.environ["S3_BUCKET"]
for attempt in range(60):
    try:
        client.create_bucket(Bucket=bucket)
        break
    except ClientError as error:
        if error.response["Error"]["Code"] in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            break
        if attempt == 59:
            raise
        time.sleep(1)
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)
print("Local demo bucket is ready")
