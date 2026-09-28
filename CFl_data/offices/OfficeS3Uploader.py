import boto3
from botocore.config import Config
import json
import os
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError
import aiohttp
import asyncio
from urllib.parse import urlparse
import sys

# Add parent directory to path to import scraper_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scraper_utils import get_random_headers


class OfficeS3Uploader:
    """
    Handles uploading Excel files to Cloudflare R2 with date-based partitioning for offices.
    Files are organized in: r2://bucket/boshamlan-data/offices/year=YYYY/month=MM/day=DD/
    """
    
    def __init__(self, bucket_name=None, r2_access_key_id=None,
                 r2_secret_access_key=None, r2_endpoint_url=None):
        """
        Initialize Cloudflare R2 uploader.

        Args:
            bucket_name: Name of the R2 bucket
            r2_access_key_id: R2 access key (optional, can use environment variables)
            r2_secret_access_key: R2 secret key (optional, can use environment variables)
            r2_endpoint_url: R2 endpoint URL (optional, can use environment variables)
        """
        self.bucket_name = bucket_name or os.environ.get('CF_R2_BUCKET_NAME')
        if not self.bucket_name:
            raise Exception("R2 bucket name is required. Set CF_R2_BUCKET_NAME environment variable.")
        self.base_path = 'boshamlan-data/offices'
        self.json_folder = 'json version'

        # Get credentials from parameters or environment variables
        access_key = r2_access_key_id or os.environ.get('CF_R2_ACCESS_KEY_ID')
        secret_key = r2_secret_access_key or os.environ.get('CF_R2_SECRET_ACCESS_KEY')
        endpoint_url = r2_endpoint_url or os.environ.get('CF_R2_ENDPOINT_URL')

        if not endpoint_url:
            raise Exception("Cloudflare R2 endpoint URL is required. Set CF_R2_ENDPOINT_URL environment variable.")

        # Initialize R2 client (S3-compatible)
        try:
            if access_key and secret_key:
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=endpoint_url,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name='us-east-1',
                    config=Config(
                        signature_version='s3v4',
                        s3={'addressing_style': 'path'}
                    )
                )
                print(f"R2 client initialized with provided credentials")
            else:
                raise Exception("Cloudflare R2 requires explicit credentials. Set CF_R2_ACCESS_KEY_ID and CF_R2_SECRET_ACCESS_KEY.")
        except NoCredentialsError:
            raise Exception("Cloudflare R2 credentials not found. Please configure credentials.")
    
    def _build_date_partition(self, upload_date=None):
        if upload_date is None:
            upload_date = datetime.now()
        return f"year={upload_date.year}/month={upload_date.month:02d}/day={upload_date.day:02d}"

    def _build_partitioned_key(self, folder_name, file_name, upload_date=None):
        date_partition = self._build_date_partition(upload_date)
        return f"{self.base_path}/{date_partition}/{folder_name}/{file_name}"

    def upload_excel_file(self, file_path, upload_date=None):
        """
        Upload an Excel file to S3 with date partitioning in 'excel files' folder.
        
        Args:
            file_path: Local path to the Excel file
            upload_date: Date for partitioning (default: today)
            
        Returns:
            S3 URL of the uploaded file
        """
        if upload_date is None:
            upload_date = datetime.now()
        
        file_name = os.path.basename(file_path)
        s3_key = self._build_partitioned_key('excel files', file_name, upload_date)
        
        try:
            # Upload file
            print(f"Uploading {file_name} to r2://{self.bucket_name}/{s3_key}")
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            
            # Generate R2 URL
            s3_url = f"r2://{self.bucket_name}/{s3_key}"
            print(f"Successfully uploaded to {s3_url}")
            
            return s3_url
            
        except FileNotFoundError:
            raise Exception(f"File not found: {file_path}")
        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {e}")
    
    def upload_image(self, file_path, image_name, office_folder_name, upload_date=None):
        """
        Upload an image file to S3 in images/office_name/ structure.
        
        Args:
            file_path: Local path to the image file
            image_name: Name for the image file in S3
            office_folder_name: Name of the office folder
            upload_date: Date for partitioning (default: today)
            
        Returns:
            S3 URL of the uploaded image
        """
        if upload_date is None:
            upload_date = datetime.now()
        
        # Create S3 key: images/office_name/image.jpg
        year = upload_date.strftime('%Y')
        month = upload_date.strftime('%m')
        day = upload_date.strftime('%d')
        
        s3_key = f"{self.base_path}/year={year}/month={month}/day={day}/images/{office_folder_name}/{image_name}"
        
        try:
            # Upload file
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            
            # Generate R2 URL
            s3_url = f"r2://{self.bucket_name}/{s3_key}"
            
            return s3_url
            
        except FileNotFoundError:
            raise Exception(f"File not found: {file_path}")
        except ClientError as e:
            raise Exception(f"Failed to upload to R2: {e}")
    
    def upload_json_file(self, json_data, file_name, upload_date=None):
        """Upload a JSON payload to the date-partitioned 'json version' folder."""
        s3_key = self._build_partitioned_key(self.json_folder, file_name, upload_date)
        body = json.dumps(json_data, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=body,
                ContentType="application/json",
            )
            s3_url = f"r2://{self.bucket_name}/{s3_key}"
            print(f"Uploaded JSON file to {s3_url}")
            return s3_url
        except ClientError as e:
            print(f"Failed to upload JSON file: {e}")
            return None

    def upload_json_file_from_path(self, file_path, file_name, upload_date=None):
        """Read a local JSON file and upload it under the partitioned 'json version' folder."""
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as handle:
                json_data = json.load(handle)
            return self.upload_json_file(json_data, file_name, upload_date)
        except Exception as e:
            print(f"Failed to read JSON file {file_path}: {e}")
            return None

    def upload_multiple_files(self, file_paths, upload_date=None):
        """
        Upload multiple Excel files to S3.
        
        Args:
            file_paths: List of local file paths
            upload_date: Date for partitioning (default: today)
            
        Returns:
            List of S3 URLs
        """
        uploaded_urls = []
        
        for file_path in file_paths:
            try:
                s3_url = self.upload_excel_file(file_path, upload_date)
                uploaded_urls.append(s3_url)
            except Exception as e:
                print(f"Error uploading {file_path}: {e}")
        
        return uploaded_urls

    def upload_json_summary(self, summary: dict, upload_date=None, filename: str | None = None):
        """Upload daily JSON summary under json-files/ for monitor ad counting."""
        if upload_date is None:
            upload_date = datetime.now()

        if filename is None:
            filename = f"summary_{upload_date.strftime('%Y%m%d')}.json"
        s3_key = self._build_partitioned_key('json-files', filename, upload_date)

        body = json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=body,
                ContentType="application/json",
            )
            s3_url = f"r2://{self.bucket_name}/{s3_key}"
            print(f"Uploaded JSON summary to {s3_url}")
            return s3_url
        except ClientError as e:
            print(f"Failed to upload JSON summary: {e}")
            return None
    
    def verify_bucket_exists(self):
        """
        Verify that the S3 bucket exists.
        
        Returns:
            True if bucket exists, False otherwise
        """
        try:
            self.s3_client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)
            return True
        except ClientError:
            return False
    
    async def download_and_upload_image(self, image_url, office_folder_name, listing_index, upload_date=None):
        """
        Download an image from URL and upload to S3.
        
        Args:
            image_url: URL of the image to download
            office_folder_name: Name of the office folder
            listing_index: Index of the listing (for unique naming)
            upload_date: Date for partitioning (default: today)
            
        Returns:
            S3 URL of the uploaded image or None if failed
        """
        if not image_url or image_url.strip() == '':
            return None
        
        try:
            # Parse the URL to get the file extension
            parsed_url = urlparse(image_url)
            path = parsed_url.path
            
            # Get file extension from URL
            ext = os.path.splitext(path)[1]
            if not ext or ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
                ext = '.jpg'  # Default extension
            
            # Create unique image name
            image_name = f"listing_{listing_index}{ext}"
            
            # Get random headers for the request
            headers = get_random_headers()
            
            # Download image
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        # Create temp directory
                        temp_dir = 'temp_images'
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        # Save temporarily
                        temp_path = os.path.join(temp_dir, image_name)
                        with open(temp_path, 'wb') as f:
                            f.write(await response.read())
                        
                        # Upload to S3
                        s3_url = self.upload_image(temp_path, image_name, office_folder_name, upload_date)
                        
                        # Delete temp file
                        os.remove(temp_path)
                        
                        return s3_url
                    else:
                        print(f"    Failed to download image: HTTP {response.status}")
                        return None
        except Exception as e:
            print(f"    Error downloading/uploading image: {e}")
            return None


def main():
    """Test the R2 uploader"""
    uploader = OfficeS3Uploader()
    
    # Verify bucket exists
    if uploader.verify_bucket_exists():
        print(f"Bucket '{uploader.bucket_name}' exists and is accessible")
    else:
        print(f"Warning: Bucket '{uploader.bucket_name}' does not exist or is not accessible")


if __name__ == "__main__":
    main()
