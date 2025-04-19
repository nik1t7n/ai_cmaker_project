import os
import uuid
from services.s3 import S3Service
from typing import Optional
import httpx


async def download_from_url_and_to_s3(url: str, content_type: str = "video/mp4", key: Optional[str] = None):

    async with httpx.AsyncClient(timeout=10) as client:

        response = await client.get(url)
        response.raise_for_status()
        data_in_bytes = response.content 

    
    s3_service = S3Service(
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        access_key=os.getenv("S3_ACCESS_KEY"),
        secret_key=os.getenv("S3_SECRET_KEY"),
        region=os.getenv("S3_REGION_NAME"),
        bucket_name=os.getenv("S3_BUCKET_NAME"),
    )

    random_key = f"{uuid.uuid4}.mp4"
    video_upload_result = await s3_service.upload_file(
        key=f"{key or random_key}",
        data=data_in_bytes,
        content_type=content_type,
    )

    if video_upload_result["status"] != 200:
        raise Exception(f"Failed to upload video to S3: {video_upload_result}")

    return True 
