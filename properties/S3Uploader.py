import boto3
import os
from datetime import datetime, timedelta
from botocore.exceptions import ClientError, NoCredentialsError
import aiohttp
import asyncio
from urllib.parse import urlparse
import sys

# Add parent directory to path to import scraper_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import get_random_headers, random_short_delay


class S3Uploader:
    """
    Handles uploading Excel files to AWS S3 with date-based partitioning.
    Files are organized in the structure: s3://bucket/boshamlan-data/properties/date/filename.xlsx
    """
    
    def __init__(self, bucket_name='data-collection-dl', aws_access_key_id=None, aws_secret_access_key=None, region_name='us-east-1'):
        """
        Initialize S3 uploader.
        
        Args:
            bucket_name: Name of the S3 bucket
            aws_access_key_id: AWS access key (optional, can use environment variables)
            aws_secret_access_key: AWS secret key (optional, can use environment variables)
            region_name: AWS region name
        """
        self.bucket_name = bucket_name
        self.base_path = 'boshamlan-data/properties'
        self.excel_folder = 'excel files'
        self.images_folder = 'images'
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
                # Use default credentials chain (env vars, credentials file, IAM role)
                self.s3_client = boto3.client('s3', region_name=region_name)
                print(f"S3 client initialized with default credentials for region '{region_name}'")
        except NoCredentialsError:
            print("ERROR: No AWS credentials found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.")
            raise
        except Exception as e:
            print(f"ERROR: Failed to initialize S3 client: {e}")
            raise
    
    def upload_file(self, file_path, category_name):
        """
        Upload a file to S3 with date partitioning.
        
        Args:
            file_path: Local path to the file to upload
            category_name: Category name (rent, sale, exchange) which will be the filename
        
        Returns:
            S3 URI of the uploaded file or None if failed
        """
        try:
            # Verify file exists before attempting upload
            if not os.path.exists(file_path):
                print(f"ERROR: File not found: {file_path}")
                return None
            
            # Get file size for logging
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Get today's date for partitioning: year=YYYY/month=MM/day=DD
            now = datetime.now()
            date_partition = f"year={now.year}/month={now.month:02d}/day={now.day:02d}"
            
            # Construct S3 key: boshamlan-data/properties/year=2026/month=01/day=05/excel files/rent.xlsx
            s3_key = f"{self.base_path}/{date_partition}/{self.excel_folder}/{category_name}.xlsx"
            
            print(f"Uploading {file_path} ({file_size_mb:.2f} MB) to S3...")
            
            # Upload the file with metadata
            extra_args = {
                'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'Metadata': {
                    'upload-date': datetime.now().isoformat(),
                    'category': category_name,
                    'source': 'boshamlan-scraper'
                }
            }
            
            self.s3_client.upload_file(
                file_path, 
                self.bucket_name, 
                s3_key,
                ExtraArgs=extra_args
            )
            
            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            print(f"✓ Successfully uploaded to {s3_uri}")
            return s3_uri
            
        except FileNotFoundError:
            print(f"ERROR: File not found: {file_path}")
            return None
        except NoCredentialsError:
            print(f"ERROR: AWS credentials not configured properly")
            return None
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            print(f"ERROR: AWS S3 error while uploading {file_path}")
            print(f"  Error Code: {error_code}")
            print(f"  Message: {error_msg}")
            return None
        except Exception as e:
            print(f"ERROR: Unexpected error while uploading {file_path}: {e}")
            return None
    
    def upload_multiple_files(self, file_dict):
        """
        Upload multiple files to S3.
        
        Args:
            file_dict: Dictionary with category names as keys and file paths as values
                      Example: {'rent': 'path/to/rent.xlsx', 'sale': 'path/to/sale.xlsx'}
        
        Returns:
            Dictionary with category names and their S3 URIs
        """
        if not file_dict:
            print("WARNING: No files provided for upload")
            return {}
        
        print(f"\nUploading {len(file_dict)} file(s) to S3...")
        results = {}
        failed = []
        
        for category, file_path in file_dict.items():
            s3_uri = self.upload_file(file_path, category)
            if s3_uri:
                results[category] = s3_uri
            else:
                failed.append(category)
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Upload Summary: {len(results)}/{len(file_dict)} successful")
        if failed:
            print(f"Failed uploads: {', '.join(failed)}")
        print(f"{'='*60}")
        
        return results
    
    def check_bucket_exists(self):
        """
        Check if the S3 bucket exists and is accessible.
        
        Returns:
            True if bucket exists and is accessible, False otherwise
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"✓ Bucket '{self.bucket_name}' exists and is accessible in region '{self.region_name}'")
            return True
        except NoCredentialsError:
            print(f"ERROR: AWS credentials not configured")
            return False
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"ERROR: Bucket '{self.bucket_name}' does not exist")
            elif error_code == '403':
                print(f"ERROR: Access denied to bucket '{self.bucket_name}'")
                print("  Check IAM permissions for s3:ListBucket and s3:PutObject")
            else:
                print(f"ERROR: Failed to access bucket: {e}")
            return False
        except Exception as e:
            print(f"ERROR: Unexpected error checking bucket: {e}")
            return False
    
    def list_uploaded_files(self, date_partition=None):
        """
        List files uploaded for a specific date partition.
        
        Args:
            date_partition: Date string (YYYY-MM-DD). If None, uses today's date.
        
        Returns:
            List of S3 keys for the date partition
        """
        if date_partition is None:
            date_partition = datetime.now().strftime("%Y-%m-%d")
        
        prefix = f"{self.base_path}/{date_partition}/"
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
                print(f"Found {len(files)} file(s) for date {date_partition}:")
                for file_key in files:
                    print(f"  - s3://{self.bucket_name}/{file_key}")
                return files
            else:
                print(f"No files found for date {date_partition}")
                return []
                
        except ClientError as e:
            print(f"ERROR: Failed to list files: {e}")
            return []
        except Exception as e:
            print(f"ERROR: Unexpected error listing files: {e}")
            return []
    
    async def download_image(self, image_url, timeout=10):
        """
        Download an image from a URL.
        
        Args:
            image_url: URL of the image to download
            timeout: Request timeout in seconds
        
        Returns:
            Tuple of (image_data, content_type) or (None, None) if failed
        """
        try:
            # Get random headers for the request
            headers = get_random_headers()
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        content_type = response.headers.get('Content-Type', 'image/jpeg')
                        return image_data, content_type
                    else:
                        print(f"Failed to download image: HTTP {response.status}")
                        return None, None
        except Exception as e:
            print(f"Error downloading image from {image_url}: {e}")
            return None, None
    
    async def upload_image(self, image_url, filename=None, category_name=None):
        """
        Download and upload an image to S3 in the images folder.
        
        Args:
            image_url: URL of the image to download and upload
            filename: Optional custom filename. If not provided, generates from URL
            category_name: Optional category name to organize images
        
        Returns:
            S3 URI of the uploaded image or None if failed
        """
        try:
            # Download the image
            image_data, content_type = await self.download_image(image_url)
            if not image_data:
                return None
            
            # Generate filename if not provided
            if not filename:
                parsed_url = urlparse(image_url)
                filename = os.path.basename(parsed_url.path)
                if not filename or '.' not in filename:
                    # Generate filename from timestamp if URL doesn't have a good filename
                    ext = content_type.split('/')[-1] if '/' in content_type else 'jpg'
                    filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{ext}"
            
            # Get today's date for partitioning
            now = datetime.now()
            date_partition = f"year={now.year}/month={now.month:02d}/day={now.day:02d}"
            
            # Construct S3 key: boshamlan-data/properties/year=2026/month=01/day=05/images/[category]/filename.jpg
            if category_name:
                s3_key = f"{self.base_path}/{date_partition}/{self.images_folder}/{category_name}/{filename}"
            else:
                s3_key = f"{self.base_path}/{date_partition}/{self.images_folder}/{filename}"
            
            # Upload to S3
            extra_args = {
                'ContentType': content_type,
                'Metadata': {
                    'upload-date': datetime.now().isoformat(),
                    'source-url': image_url[:1000],  # Limit length
                    'source': 'boshamlan-scraper'
                }
            }
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=image_data,
                **extra_args
            )
            
            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            return s3_uri
            
        except Exception as e:
            print(f"Error uploading image {image_url}: {e}")
            return None
    
    async def upload_images_from_data(self, cards_data, category_name):
        """
        Upload all images from scraped card data.
        
        Args:
            cards_data: List of card dictionaries with 'image_url' field
            category_name: Category name for organizing images
        
        Returns:
            Dictionary mapping original URLs to S3 URIs
        """
        if not cards_data:
            return {}
        
        print(f"\nUploading images for category '{category_name}'...")
        results = {}
        
        for i, card in enumerate(cards_data):
            image_url = card.get('image_url')
            if not image_url:
                continue
            
            # Generate a unique filename based on card index and timestamp
            title = card.get('title', '')
            # Create a safe filename from title (first 30 chars)
            safe_title = ''.join(c for c in title[:30] if c.isalnum() or c in (' ', '_')).strip().replace(' ', '_')
            if safe_title:
                filename = f"{safe_title}_{i}.jpg"
            else:
                filename = f"property_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            
            print(f"  Uploading image {i+1}/{len(cards_data)}...")
            s3_uri = await self.upload_image(image_url, filename, category_name)
            
            if s3_uri:
                results[image_url] = s3_uri
                print(f"    ✓ Uploaded to {s3_uri}")
            else:
                print(f"    ✗ Failed to upload image {i+1}")
            
            # Random delay between image downloads (0.3-1.0 seconds)
            await random_short_delay(0.3, 1.0)
        
        print(f"\n✓ Successfully uploaded {len(results)}/{len(cards_data)} images")
        return results
