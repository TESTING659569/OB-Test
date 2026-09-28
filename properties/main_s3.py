import asyncio
import os
from datetime import datetime
from CategoryScraper import CategoryScraper
from S3Uploader import S3Uploader
import sys

# Add parent directory to path to import scraper_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import random_delay


class MainS3Scraper:
    """
    Main orchestrator for scraping Boshamlan data and uploading to AWS S3.
    
    This script:
    1. Scrapes data from all categories (rent, sale, exchange) filtered by yesterday's date
    2. Creates Excel files with sheets for each subcategory
    3. Uploads files to S3 with date-based partitioning
    """
    
    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None):
        """
        Initialize the main scraper.
        
        Args:
            aws_access_key_id: AWS access key (optional, can use environment variables)
            aws_secret_access_key: AWS secret key (optional, can use environment variables)
        """
        self.category_scraper = CategoryScraper()
        
        # Get AWS credentials from environment if not provided
        access_key = aws_access_key_id or os.environ.get('AWS_ACCESS_KEY_ID')
        secret_key = aws_secret_access_key or os.environ.get('AWS_SECRET_ACCESS_KEY')
        
        self.s3_uploader = S3Uploader(
            bucket_name='data-collection-dl',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
    
    async def run(self):
        """
        Main execution method:
        1. Scrapes all categories and subcategories
        2. Uploads images to S3 in 'images' folder
        3. Creates Excel files with image_s3_path column
        4. Uploads Excel files to S3 in 'excel files' folder
        """
        print("="*80)
        print("BOSHAMLAN SCRAPER - S3 Edition")
        print("="*80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Target S3: s3://data-collection-dl/boshamlan-data/properties/")
        print("  - Excel files -> year=YYYY/month=MM/day=DD/excel files/")
        print("  - Images -> year=YYYY/month=MM/day=DD/images/")
        print("="*80)
        
        # Step 1: Check S3 bucket accessibility
        print("\n[1/4] Checking S3 bucket accessibility...")
        if not self.s3_uploader.check_bucket_exists():
            print("ERROR: Cannot access S3 bucket. Please check your AWS credentials and bucket permissions.")
            return
        
        # Step 2: Scrape all categories (don't save Excel yet)
        print("\n[2/4] Scraping data from all categories...")
        # First scrape without saving to Excel
        for category_name in self.category_scraper.categories.keys():
            print(f"\n{'#'*70}")
            print(f"# Scraping Category: {category_name.upper()}")
            print(f"{'#'*70}\n")
            
            await self.category_scraper.scrape_category(category_name)
            # Random delay between categories (2-4 seconds)
            await random_delay(2.0, 4.0)
        
        if not self.category_scraper.last_scraped_data:
            print("WARNING: No data was scraped. Nothing to upload.")
            return
        
        print(f"\n✓ Successfully scraped {len(self.category_scraper.last_scraped_data)} category(ies)")
        
        # Step 3: Upload images to S3 and get mappings
        print("\n[3/4] Uploading images to S3...")
        image_s3_mappings = {}
        total_images = 0
        
        for category_name, category_data in self.category_scraper.last_scraped_data.items():
            # Get all cards data for this category
            all_cards = []
            for subcat_name, subcat_data in category_data.items():
                all_cards.extend(subcat_data)
            
            if all_cards:
                image_results = await self.s3_uploader.upload_images_from_data(all_cards, category_name)
                image_s3_mappings[category_name] = image_results
                total_images += len(image_results)
        
        print(f"\n✓ Successfully uploaded {total_images} image(s) to S3")
        
        # Step 4: Create Excel files with image_s3_path column
        print("\n[4/4] Creating and uploading Excel files...")
        excel_files = {}
        
        for category_name, category_data in self.category_scraper.last_scraped_data.items():
            category_image_mapping = image_s3_mappings.get(category_name, {})
            file_path = self.category_scraper.save_to_excel(category_name, category_data, category_image_mapping)
            if file_path:
                excel_files[category_name] = file_path
        
        if not excel_files:
            print("WARNING: No Excel files were generated.")
            return
        
        print(f"\n✓ Successfully created {len(excel_files)} Excel file(s)")
        
        # Upload Excel files to S3
        upload_results = self.s3_uploader.upload_multiple_files(excel_files)
        
        if upload_results:
            print(f"\n✓ Successfully uploaded {len(upload_results)} Excel file(s) to S3:")
            for category, s3_uri in upload_results.items():
                print(f"  - {category}: {s3_uri}")
        else:
            print("\nERROR: Failed to upload Excel files to S3.")
        
        # Summary
        print("\n" + "="*80)
        print("SCRAPING COMPLETED")
        print("="*80)
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Categories processed: {len(excel_files)}")
        print(f"Images uploaded to S3: {total_images}")
        print(f"Excel files uploaded to S3: {len(upload_results)}")
        print("="*80)


async def main():
    """
    Entry point for the scraper.
    
    AWS credentials can be provided via:
    1. Environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
    2. AWS credentials file (~/.aws/credentials)
    3. IAM role (if running on EC2)
    """
    # Option 1: Use environment variables or default credentials
    scraper = MainS3Scraper()
    
    # Option 2: Provide credentials explicitly (not recommended for production)
    # scraper = MainS3Scraper(
    #     aws_access_key_id='your-access-key',
    #     aws_secret_access_key='your-secret-key'
    # )
    
    await scraper.run()


if __name__ == "__main__":
    """
    Usage:
    
    1. Set environment variables (recommended):
       export AWS_ACCESS_KEY_ID=your-access-key
       export AWS_SECRET_ACCESS_KEY=your-secret-key
       python main_s3.py
    
    2. Or use AWS credentials file:
       Configure ~/.aws/credentials
       python main_s3.py
    
    3. For Windows PowerShell:
       $env:AWS_ACCESS_KEY_ID="your-access-key"
       $env:AWS_SECRET_ACCESS_KEY="your-secret-key"
       python main_s3.py
    """
    asyncio.run(main())
