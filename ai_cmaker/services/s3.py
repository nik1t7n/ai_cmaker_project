import logging
import aioboto3
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class S3Service:
    """Service for interacting with S3 storage using aioboto3"""
    
    def __init__(self, 
                 endpoint_url: str,
                 access_key: str,
                 secret_key: str,
                 region: str,
                 bucket_name: str):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.bucket_name = bucket_name
        
        self.session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

    async def upload_file(self, key: str, data: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload bytes data to S3
        
        Args:
            key: S3 object key (path in bucket)
            data: Bytes data to upload
            content_type: Optional content type (MIME type)
            
        Returns:
            Dictionary with status and URL
        """
        logger.info(f"[S3Service] Uploading file with key: {key} ({len(data)} bytes)")
        
        if not data:
            raise ValueError("Empty data for upload")
            
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
                
            async with self.session.client('s3', endpoint_url=self.endpoint_url) as s3:
                response = await s3.put_object(
                    Bucket=self.bucket_name, 
                    Key=key, 
                    Body=data,
                    **extra_args
                )
                
            logger.info(f"[S3Service] File successfully uploaded: {key}")
            
            return {
                'status': 200,
                'url': f"{self.endpoint_url}/{self.bucket_name}/{key}"
            }
            
        except Exception as e:
            logger.error(f"[S3Service] S3 upload error: {str(e)}", exc_info=True)
            raise

    async def download_file(self, key: str) -> bytes:
        """
        Download file from S3
        
        Args:
            key: S3 object key to download
            
        Returns:
            File content as bytes
        """
        logger.info(f"[S3Service] Downloading file with key: {key}")
        
        try:
            async with self.session.client('s3', endpoint_url=self.endpoint_url) as s3:
                response = await s3.get_object(Bucket=self.bucket_name, Key=key)
                data = await response['Body'].read()
                
            logger.info(f"[S3Service] File downloaded: {key} ({len(data)} bytes)")
            return data
            
        except Exception as e:
            logger.error(f"[S3Service] S3 download error: {str(e)}", exc_info=True)
            raise

    async def delete_file(self, key: str) -> Dict[str, Any]:
        """
        Delete file from S3
        
        Args:
            key: S3 object key to delete
            
        Returns:
            Dictionary with status
        """
        logger.info(f"[S3Service] Deleting file with key: {key}")
        
        try:
            async with self.session.client('s3', endpoint_url=self.endpoint_url) as s3:
                response = await s3.delete_object(Bucket=self.bucket_name, Key=key)  # noqa: F841
                
            logger.info(f"[S3Service] File deleted: {key}")
            return {'status': 'success'}
            
        except Exception as e:
            logger.error(f"[S3Service] S3 delete error: {str(e)}", exc_info=True)
            raise

    def get_url(self, key: str) -> str:
        """
        Get the URL for an object in S3
        
        Args:
            key: S3 object key
            
        Returns:
            Full URL to the object
        """
        return f"{self.endpoint_url}/{self.bucket_name}/{key}"