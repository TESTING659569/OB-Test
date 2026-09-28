import boto3
import os
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError
import aiohttp
import asyncio
from urllib.parse import urlparse
import sys

# Add parent directory to path to import scraper_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import get_random_headers


class OfficeS3Uploader:
    """
    Handles uploading Excel files to AWS S3 with date-based partitioning for offices.
    Files are organized in: s3://bucket/boshamlan-data/offices/year=YYYY/month=MM/day=DD/
    """
    
    def __init__(self, bucket_name='data-collection-dl', aws_access_key_id=None, 
                 aws_secret_access_key=None, region_name='us-east-1'):
        """
        Initialize S3 uploader.
        
        Args:
            bucket_name: Name of the S3 bucket
            aws_access_key_id: AWS access key (optional, can use environment variables)
            aws_secret_access_key: AWS secret key (optional, can use environment variables)
            region_name: AWS region name
        """
        self.bucket_name = bucket_name
        self.base_path = 'boshamlan-data/offices'
        self.region_name = region_name
        
        # Get credentials from parameters or environment variables
        access_key = aws_access_key_id or os.environ.get('AWS_ACCESS_KEY_ID')
        secret_key = aws_secret_access_key or os.environ.get('AWS_SECRET_ACCESS_KEY')
        
        # Initialize S3 client
        try:
            if access_key and secret_key:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=region_name
                )
                print(f"S3 client initialized with provided credentials for region '{region_name}'")
            else:
                # Use default credentials chain
                self.s3_client = boto3.client('s3', region_name=region_name)
                print(f"S3 client initialized with default credentials for region '{region_name}'")
        except NoCredentialsError:
            raise Exception("AWS credentials not found. Please configure credentials.")
    
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
        
        # Create S3 key with date partitioning and excel files folder
        year = upload_date.strftime('%Y')
        month = upload_date.strftime('%m')
        day = upload_date.strftime('%d')
        
        file_name = os.path.basename(file_path)
        s3_key = f"{self.base_path}/year={year}/month={month}/day={day}/excel files/{file_name}"
        
        try:
            # Upload file
            print(f"Uploading {file_name} to s3://{self.bucket_name}/{s3_key}")
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            
            # Generate S3 URL
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
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
            
            # Generate S3 URL
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
            
            return s3_url
            
        except FileNotFoundError:
            raise Exception(f"File not found: {file_path}")
        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {e}")
    
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
    
    def verify_bucket_exists(self):
        """
        Verify that the S3 bucket exists.
        
        Returns:
            True if bucket exists, False otherwise
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
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
    """Test the S3 uploader"""
    uploader = OfficeS3Uploader()
    
    # Verify bucket exists
    if uploader.verify_bucket_exists():
        print(f"Bucket '{uploader.bucket_name}' exists and is accessible")
    else:
        print(f"Warning: Bucket '{uploader.bucket_name}' does not exist or is not accessible")


if __name__ == "__main__":
    main()
