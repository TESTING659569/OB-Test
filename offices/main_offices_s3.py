import asyncio
import os
import sys
from datetime import datetime, timedelta
import shutil
import pandas as pd

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from offices.OfficeScraper import OfficeScraper
from offices.OfficeS3Uploader import OfficeS3Uploader


def calculate_relative_date(date_str):
    """Calculate relative date from ISO datetime string."""
    try:
        # Parse ISO datetime
        dt = datetime.fromisoformat(date_str.replace('+03:00', ''))
        now = datetime.now()
        diff = now - dt
        
        if diff.days == 0:
            hours = diff.seconds // 3600
            if hours == 0:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.days == 1:
            return "yesterday"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif diff.days < 365:
            months = diff.days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = diff.days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"
    except:
        return ""


def format_date(date_str):
    """Format ISO datetime to simple date format."""
    try:
        # Parse ISO datetime and format as DD-MM-YYYY
        dt = datetime.fromisoformat(date_str.replace('+03:00', ''))
        return dt.strftime('%d-%m-%Y')
    except:
        return date_str


class OfficeDataPipeline:
    """
    Complete pipeline for scraping office data, generating Excel files, and uploading to S3.
    """
    
    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None, region_name='us-east-1'):
        """
        Initialize the pipeline.
        
        Args:
            aws_access_key_id: AWS access key (optional)
            aws_secret_access_key: AWS secret key (optional)
            region_name: AWS region name
        """
        self.scraper = OfficeScraper()
        self.s3_uploader = OfficeS3Uploader(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        self.temp_dir = 'temp_offices_excel'
    
    def _clean_filename(self, name):
        """
        Clean office name to create valid filename.
        
        Args:
            name: Office name
            
        Returns:
            Cleaned filename
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        
        # Limit length
        if len(name) > 100:
            name = name[:100]
        
        # Remove leading/trailing spaces
        name = name.strip()
        
        return name
    
    def generate_office_excel(self, office_data, output_dir):
        """
        Generate Excel file for a single office using pandas.
        
        Args:
            office_data: Dictionary containing office info and listings
            output_dir: Directory to save Excel file
            
        Returns:
            Path to the generated Excel file
        """
        office_name = office_data.get('name', 'Unknown Office')
        safe_name = self._clean_filename(office_name)
        
        # Extract unique identifier from URL to avoid filename collisions
        office_url = office_data.get('url', '')
        url_id = office_url.split('/')[-1] if office_url else ''
        
        # Combine office name with URL ID to ensure uniqueness
        if url_id:
            excel_path = os.path.join(output_dir, f"{safe_name}_{url_id}.xlsx")
        else:
            excel_path = os.path.join(output_dir, f"{safe_name}.xlsx")
        
        # Create info sheet data with columns as headers
        info_data = {
            'Name': [office_data.get('name', '')],
            'URL': [office_data.get('url', '')],
            'Description': [office_data.get('description', '')],
            'Telephone': [office_data.get('telephone', '')],
            'Email': [office_data.get('email', '')],
            'Image': [office_data.get('image', '')],
            'Instagram': [office_data.get('instagram', '')],
            'Website': [office_data.get('website', '')],
            'Ads Number': [office_data.get('ads_number', 0)]
        }
        df_info = pd.DataFrame(info_data)
        
        # Create main sheet data
        listings = office_data.get('listings', [])
        main_data = []
        for listing in listings:
            date_published = listing.get('datePublished', '')
            main_data.append({
                'Name': listing.get('name', ''),
                'URL': listing.get('url', ''),
                'Description': listing.get('description', ''),
                'Image URL': listing.get('image_url', ''),
                'Price': listing.get('price', ''),
                'Address Region': listing.get('addressRegion', ''),
                'Address Locality': listing.get('addressLocality', ''),
                'Views': listing.get('views', ''),
                'Date Published': format_date(date_published),
                'Relative Date': calculate_relative_date(date_published),
                'S3 Image Path': listing.get('s3_image_url', '')
            })
        df_main = pd.DataFrame(main_data)
        
        # Write to Excel with two sheets
        with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
            df_info.to_excel(writer, sheet_name='info', index=False)
            df_main.to_excel(writer, sheet_name='main', index=False)
        
        print(f"Generated Excel file: {excel_path}")
        return excel_path
    
    async def run_pipeline(self, filter_date=None, upload_to_s3=True):
        """
        Run the complete pipeline.
        
        Args:
            filter_date: Date to filter listings (default: yesterday)
            upload_to_s3: Whether to upload to S3 (default: True)
            
        Returns:
            Dictionary with pipeline results
        """
        # Default to yesterday
        if filter_date is None:
            filter_date = datetime.now() - timedelta(days=1)
        
        print("="*80)
        print(f"OFFICE DATA PIPELINE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        print(f"Filter date: {filter_date.strftime('%Y-%m-%d')}")
        print(f"Upload to S3: {upload_to_s3}")
        print("="*80 + "\n")
        
        # Step 1: Scrape office data
        print("STEP 1: Scraping office data from boshamlan.com")
        print("-" * 80)
        
        offices_data = await self.scraper.scrape_all_offices(filter_date=filter_date)
        
        if not offices_data:
            print("\n⚠ No offices found")
            return {
                'success': False,
                'message': 'No offices found',
                'offices_count': 0,
                'files_generated': 0,
                'files_uploaded': 0,
                'images_uploaded': 0
            }
        
        print(f"\n✓ Found {len(offices_data)} offices")
        
        total_listings = sum(len(office.get('listings', [])) for office in offices_data)
        print(f"✓ Total listings from {filter_date.strftime('%Y-%m-%d')}: {total_listings}")
        
        # Step 2: Upload images to S3
        uploaded_images_count = 0
        if upload_to_s3:
            print("\n" + "="*80)
            print("STEP 2: Uploading images to S3")
            print("-" * 80)
            
            for office in offices_data:
                office_name = office.get('name', 'Unknown')
                office_folder_name = self._clean_filename(office_name)
                listings = office.get('listings', [])
                
                for idx, listing in enumerate(listings, 1):
                    image_url = listing.get('image_url', '')
                    if image_url:
                        print(f"  Uploading image {idx}/{len(listings)} for {office_name}...")
                        s3_image_url = await self.s3_uploader.download_and_upload_image(
                            image_url, 
                            office_folder_name, 
                            idx
                        )
                        if s3_image_url:
                            listing['s3_image_url'] = s3_image_url
                            uploaded_images_count += 1
                        # Random delay between image downloads (0.3-0.8 seconds)
                        from scraper_utils import random_short_delay
                        await random_short_delay(0.3, 0.8)
            
            print(f"\n✓ Uploaded {uploaded_images_count} images to S3")
        
        # Step 3: Generate Excel files
        print("\n" + "="*80)
        print(f"STEP {'3' if upload_to_s3 else '2'}: Generating Excel files")
        print("-" * 80)
        
        # Create temporary directory for Excel files
        os.makedirs(self.temp_dir, exist_ok=True)
        
        excel_files = []
        for office in offices_data:
            try:
                file_path = self.generate_office_excel(office, self.temp_dir)
                excel_files.append(file_path)
            except Exception as e:
                office_name = office.get('name', 'Unknown')
                print(f"Error generating Excel for {office_name}: {e}")
        
        print(f"\n✓ Generated {len(excel_files)} Excel files")
        
        # Step 4: Upload Excel files to S3
        uploaded_urls = []
        
        if upload_to_s3 and excel_files:
            print("\n" + "="*80)
            print("STEP 4: Uploading Excel files to S3")
            print("-" * 80)
            
            # Use today's date for S3 partitioning (not filter date)
            uploaded_urls = self.s3_uploader.upload_multiple_files(excel_files)
            
            print(f"\n✓ Uploaded {len(uploaded_urls)} files to S3")
        else:
            print("\n⚠ Skipping S3 upload")
        
        # Step 5: Cleanup
        print("\n" + "="*80)
        print(f"STEP {'5' if upload_to_s3 else '3'}: Cleanup")
        print("-" * 80)
        
        if upload_to_s3:
            # Remove temporary directory
            try:
                shutil.rmtree(self.temp_dir)
                print(f"✓ Removed temporary directory: {self.temp_dir}")
            except Exception as e:
                print(f"⚠ Could not remove temporary directory: {e}")
            
            # Remove temp images directory if it exists
            try:
                if os.path.exists('temp_images'):
                    shutil.rmtree('temp_images')
                    print(f"✓ Removed temporary images directory")
            except Exception as e:
                print(f"⚠ Could not remove temporary images directory: {e}")
        else:
            print(f"✓ Excel files saved locally in: {self.temp_dir}")
        
        # Summary
        print("\n" + "="*80)
        print("PIPELINE SUMMARY")
        print("="*80)
        print(f"Offices processed: {len(offices_data)}")
        print(f"Total listings: {total_listings}")
        print(f"Excel files generated: {len(excel_files)}")
        print(f"Files uploaded to S3: {len(uploaded_urls)}")
        print(f"Images uploaded to S3: {uploaded_images_count}")
        
        print("="*80 + "\n")
        
        return {
            'success': True,
            'offices_count': len(offices_data),
            'total_listings': total_listings,
            'files_generated': len(excel_files),
            'files_uploaded': len(uploaded_urls),
            'images_uploaded': uploaded_images_count,
            'uploaded_urls': uploaded_urls,
            'local_files': excel_files if not upload_to_s3 else []
        }


async def main():
    """
    Main entry point for the office data pipeline.
    """
    # You can configure AWS credentials here or use environment variables
    # AWS credentials will be read from environment variables if not provided
    
    pipeline = OfficeDataPipeline(
        # aws_access_key_id='YOUR_ACCESS_KEY',  # Optional
        # aws_secret_access_key='YOUR_SECRET_KEY',  # Optional
        region_name='us-east-1'
    )
    
    # Run pipeline for yesterday's data (default)
    # You can also specify a custom date:
    # custom_date = datetime(2026, 1, 5)
    # results = await pipeline.run_pipeline(filter_date=custom_date)
    
    results = await pipeline.run_pipeline()
    
    if results['success']:
        print("✓ Pipeline completed successfully!")
    else:
        print("✗ Pipeline completed with warnings")


if __name__ == "__main__":
    asyncio.run(main())
