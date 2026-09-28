import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
import shutil
import pandas as pd

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# Insert CFl_data directory first so 'offices.*' resolves to R2 versions
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    Complete pipeline for scraping office data, generating Excel files, and uploading to Cloudflare R2.
    """
    
    def __init__(self, r2_access_key_id=None, r2_secret_access_key=None, r2_endpoint_url=None):
        """
        Initialize the pipeline.

        Args:
            r2_access_key_id: Cloudflare R2 access key (optional)
            r2_secret_access_key: Cloudflare R2 secret key (optional)
            r2_endpoint_url: Cloudflare R2 endpoint URL (optional)
        """
        self.scraper = OfficeScraper()
        self.s3_uploader = OfficeS3Uploader(
            r2_access_key_id=r2_access_key_id,
            r2_secret_access_key=r2_secret_access_key,
            r2_endpoint_url=r2_endpoint_url
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
    
    def generate_office_json(self, office_data, output_dir):
        """Generate a JSON file for a single office for R2 upload."""
        office_name = office_data.get('name', 'Unknown Office')
        safe_name = self._clean_filename(office_name)

        office_url = office_data.get('url', '')
        url_id = office_url.split('/')[-1] if office_url else ''

        if url_id:
            json_path = os.path.join(output_dir, f"{safe_name}_{url_id}.json")
        else:
            json_path = os.path.join(output_dir, f"{safe_name}.json")

        payload = {
            'name': office_data.get('name', ''),
            'url': office_data.get('url', ''),
            'description': office_data.get('description', ''),
            'telephone': office_data.get('telephone', ''),
            'email': office_data.get('email', ''),
            'image': office_data.get('image', ''),
            'instagram': office_data.get('instagram', ''),
            'website': office_data.get('website', ''),
            'ads_number': office_data.get('ads_number', 0),
            'listings': office_data.get('listings', []),
            'generated_at': datetime.now().isoformat(timespec='seconds')
        }

        with open(json_path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

        print(f"Generated JSON file: {json_path}")
        return json_path

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
            listing_url = listing.get('url', '')
            listing_id = listing_url.rstrip('/').split('/')[-1] if listing_url else ''
            main_data.append({
                'id': listing_id,
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
        run_started_at = datetime.now()
        
        print("="*80)
        print(f"OFFICE DATA PIPELINE (Cloudflare R2) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
        
        # Step 2: Skip image download/upload (original URLs kept in Excel/JSON)
        uploaded_images_count = 0
        print("\n" + "="*80)
        print("\nSTEP 2: Skipping image download/upload to R2")
        print("-" * 80)
        print("\n\u2713 Image upload disabled — image_url preserved in output files only")
        
        # Step 3: Generate Excel files
        print("\n" + "="*80)
        print(f"STEP {'3' if upload_to_s3 else '2'}: Generating Excel files")
        print("-" * 80)
        
        # Create temporary directory for Excel files
        os.makedirs(self.temp_dir, exist_ok=True)
        
        excel_files = []
        json_files = []
        for office in offices_data:
            try:
                file_path = self.generate_office_excel(office, self.temp_dir)
                excel_files.append(file_path)

                json_path = self.generate_office_json(office, self.temp_dir)
                if json_path:
                    json_files.append(json_path)
            except Exception as e:
                office_name = office.get('name', 'Unknown')
                print(f"Error generating Excel/JSON for {office_name}: {e}")
        
        print(f"\n✓ Generated {len(excel_files)} Excel files and {len(json_files)} JSON files")
        
        # Step 4: Upload Excel files to S3
        uploaded_urls = []
        
        if upload_to_s3 and excel_files:
            print("\n" + "="*80)
            print("STEP 4: Uploading Excel files to R2")
            print("-" * 80)
            
            # Use today's date for R2 partitioning (not filter date)
            uploaded_urls = self.s3_uploader.upload_multiple_files(excel_files)

            json_upload_urls = []
            for json_path in json_files:
                try:
                    file_name = os.path.basename(json_path)
                    s3_url = self.s3_uploader.upload_json_file_from_path(json_path, file_name)
                    if s3_url:
                        json_upload_urls.append(s3_url)
                except Exception as e:
                    print(f"Error uploading JSON file {json_path}: {e}")
            
            print(f"\n✓ Uploaded {len(uploaded_urls)} Excel files and {len(json_upload_urls)} JSON files to R2")

            elapsed_seconds = max(1, int((datetime.now() - run_started_at).total_seconds()))
            request_metrics = self.scraper.get_request_metrics()
            requests_total = int(request_metrics.get('requests_total', 0) or 0)
            requests_failed = int(request_metrics.get('requests_failed', 0) or 0)
            requests_per_min = round(requests_total / (elapsed_seconds / 60.0), 2) if elapsed_seconds > 0 else 0.0
            error_rate_pct = round((requests_failed / requests_total) * 100.0, 2) if requests_total > 0 else 0.0

            summary = {
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
                "saved_to_s3_date": datetime.now().strftime("%Y-%m-%d"),
                "total_listings": total_listings,
                "subcategories": [
                    {
                        "name": office.get("name", "Unknown"),
                        "slug": self._clean_filename(office.get("name", "unknown")),
                        "listings_count": len(office.get("listings", [])),
                    }
                    for office in offices_data
                ],
                "request_metrics": {
                    "requests_total": requests_total,
                    "requests_failed": requests_failed,
                    "requests_per_min": requests_per_min,
                    "error_rate_pct": error_rate_pct,
                    "duration_sec": elapsed_seconds,
                    "metrics_source": "runtime_http_counter",
                },
            }
            self.s3_uploader.upload_json_summary(summary)
        else:
            print("\n\u26a0 Skipping R2 upload")
        
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
        print(f"Files uploaded to R2: {len(uploaded_urls)}")
        print(f"Images uploaded to R2: {uploaded_images_count} (image upload disabled)")
        
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
    # Credentials are read from CF_R2_* environment variables
    pipeline = OfficeDataPipeline()

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
