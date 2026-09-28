import asyncio
import sys
import os
from pathlib import Path
from PropertyCardScraper import PropertyCardScraper
import json
import pandas as pd
from datetime import datetime, timedelta

# Add parent directory to path to import scraper_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import random_delay


class CategoryScraper:
    """
    Scrapes data for main categories (rent, sale, exchange) and their subcategories.
    Creates Excel files with sheets for each subcategory.
    """
    
    def __init__(self, debug=False):
        """
        Initialize category scraper with URL patterns and category definitions.
        
        Args:
            debug: Enable debug mode to save screenshots and HTML
        """
        self.debug = debug
        self.last_scraped_data = {}  # Store scraped data for image uploading
        # Define category structure
        self.categories = {
            'rent': {
                'c_param': 1,
                'subcategories': {
                    'عقارات': 1,
                    'شقة': 2,
                    'بيت': 3,
                    'أرض': 4,
                    'عمارة': 5,
                    'شاليه': 6,
                    'مزرعة': 7,
                    'تجاري': 8
                }
            },
            'sale': {
                'c_param': 2,
                'subcategories': {
                    'عقارات': 1,
                    'شقة': 2,
                    'بيت': 3,
                    'أرض': 4,
                    'عمارة': 5,
                    'شاليه': 6,
                    'مزرعة': 7,
                    'تجاري': 8
                }
            },
            'exchange': {
                'c_param': 3,
                'subcategories': {
                    'بيوت': 3,
                    'أراضي': 4
                }
            }
        }
        
        self.yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.output_dir = 'scraped_data'
        os.makedirs(self.output_dir, exist_ok=True)
    
    def build_url(self, c_param, t_param):
        """
        Build the search URL based on category and subcategory parameters.
        
        Args:
            c_param: Category parameter (1=rent, 2=sale, 3=exchange)
            t_param: Type/subcategory parameter
        
        Returns:
            Full URL string
        """
        return f"https://www.boshamlan.com/search?c={c_param}&t={t_param}"
    
    async def scrape_category(self, category_name):
        """
        Scrape all subcategories for a given main category.
        
        Args:
            category_name: Name of the category ('rent', 'sale', or 'exchange')
        
        Returns:
            Dictionary with subcategory names as keys and their scraped data as values
        """
        if category_name not in self.categories:
            print(f"Invalid category: {category_name}")
            return None
        
        category_info = self.categories[category_name]
        c_param = category_info['c_param']
        subcategories = category_info['subcategories']
        
        category_data = {}
        failed_subcats = []
        
        for subcat_name, t_param in subcategories.items():
            print(f"\n{'='*60}")
            print(f"Scraping {category_name} -> {subcat_name}")
            print(f"{'='*60}")
            
            url = self.build_url(c_param, t_param)
            print(f"URL: {url}")
            
            try:
                # Use PropertyCardScraper to scrape this URL
                scraper = PropertyCardScraper(url)
                result = await scraper.scrape_cards()
                
                if result and result != "No cards found on this page.":
                    try:
                        parsed_data = json.loads(result)
                        category_data[subcat_name] = parsed_data
                        print(f"✓ Found {len(parsed_data)} items for {subcat_name}")
                    except json.JSONDecodeError as e:
                        print(f"ERROR: Failed to parse JSON for {subcat_name}: {e}")
                        category_data[subcat_name] = []
                        failed_subcats.append(subcat_name)
                else:
                    print(f"WARNING: No data found for {subcat_name}")
                    category_data[subcat_name] = []
                    
            except Exception as e:
                print(f"ERROR: Failed to scrape {subcat_name}: {type(e).__name__}: {e}")
                category_data[subcat_name] = []
                failed_subcats.append(subcat_name)
            
            # Random delay between subcategory requests (1.5-3.5 seconds)
            await random_delay(1.5, 3.5)
        
        # Store the scraped data for later use (e.g., image uploading)
        self.last_scraped_data[category_name] = category_data
        
        # Summary for this category
        if failed_subcats:
            print(f"\n⚠ Warning: {len(failed_subcats)} subcategory(ies) failed: {', '.join(failed_subcats)}")
        
        return category_data
    
    def save_to_excel(self, category_name, category_data, image_s3_mapping=None):
        """
        Save category data to Excel file with multiple sheets for subcategories.
        
        Args:
            category_name: Name of the category ('rent', 'sale', or 'exchange')
            category_data: Dictionary with subcategory names and their data
            image_s3_mapping: Dictionary mapping image URLs to S3 URIs
        
        Returns:
            Path to the saved Excel file or None if failed
        """
        if not category_data or all(not data for data in category_data.values()):
            print(f"No data to save for category: {category_name}")
            return None
        
        try:
            file_path = os.path.join(self.output_dir, f"{category_name}.xlsx")
            
            # Create Excel writer
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                for subcat_name, data in category_data.items():
                    if data:  # Only create sheet if there's data
                        # Add image_s3_path column if we have image mappings
                        if image_s3_mapping:
                            for item in data:
                                image_url = item.get('image_url')
                                if image_url and image_url in image_s3_mapping:
                                    item['image_s3_path'] = image_s3_mapping[image_url]
                                else:
                                    item['image_s3_path'] = None
                        
                        df = pd.json_normalize(data)
                        # Excel sheet names have a 31 character limit
                        sheet_name = subcat_name[:31]
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        print(f"Added sheet '{sheet_name}' with {len(df)} rows")
                    else:
                        # Create an empty sheet with headers
                        df = pd.DataFrame(columns=['title', 'price', 'relative_date', 'description', 
                                                  'image_url', 'link', 'mobile_number', 'views_number', 'image_s3_path'])
                        sheet_name = subcat_name[:31]
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        print(f"Added empty sheet '{sheet_name}'")
            
            print(f"\nSaved {category_name} data to {file_path}")
            return file_path
            
        except Exception as e:
            print(f"Error saving Excel file for {category_name}: {e}")
            return None
    
    async def scrape_all_categories(self, image_s3_mappings=None):
        """
        Scrape all main categories (rent, sale, exchange) and save to Excel files.
        
        Args:
            image_s3_mappings: Dictionary with category names as keys and image URL->S3 URI mappings as values
        
        Returns:
            Dictionary with category names and their Excel file paths
        """
        excel_files = {}
        
        for category_name in self.categories.keys():
            print(f"\n{'#'*70}")
            print(f"# Processing Category: {category_name.upper()}")
            print(f"{'#'*70}\n")
            
            category_data = await self.scrape_category(category_name)
            
            if category_data:
                # Get image mappings for this category if available
                category_image_mapping = None
                if image_s3_mappings and category_name in image_s3_mappings:
                    category_image_mapping = image_s3_mappings[category_name]
                
                file_path = self.save_to_excel(category_name, category_data, category_image_mapping)
                if file_path:
                    excel_files[category_name] = file_path
            
            # Delay between main categories
            await asyncio.sleep(3)
        
        return excel_files


# Test function
async def test_category_scraper():
    """Test the category scraper by scraping one subcategory."""
    scraper = CategoryScraper()
    
    # Test with rent -> عقارات
    url = scraper.build_url(1, 1)
    print(f"Testing URL: {url}")
    
    property_scraper = PropertyCardScraper(url)
    result = await property_scraper.scrape_cards()
    
    if result != "No cards found on this page.":
        parsed_data = json.loads(result)
        print(f"Found {len(parsed_data)} items")
        print(json.dumps(parsed_data[:2], ensure_ascii=False, indent=2))  # Print first 2 items
    else:
        print("No data found")


if __name__ == "__main__":
    # Run test
    # asyncio.run(test_category_scraper())
    
    # Or run full scraping
    async def main():
        scraper = CategoryScraper()
        excel_files = await scraper.scrape_all_categories()
        print(f"\n\nGenerated Excel files: {excel_files}")
    
    asyncio.run(main())
