"""
Debug script to test the office scraper with a smaller sample.
This script tests each component individually without S3 upload.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import pandas as pd

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from offices.OfficeScraper import OfficeScraper


def calculate_relative_date(date_str):
    """Calculate relative date from ISO datetime string."""
    try:
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
        dt = datetime.fromisoformat(date_str.replace('+03:00', ''))
        return dt.strftime('%d-%m-%Y')
    except:
        return date_str


async def test_scraper():
    """Test the office scraper"""
    print("="*80)
    print("TESTING OFFICE SCRAPER")
    print("="*80)
    
    scraper = OfficeScraper()
    
    # Test 1: Scrape agents page
    print("\nTest 1: Scraping agents page...")
    print("-" * 80)
    
    async with asyncio.timeout(60):
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                scraper.browser = await p.chromium.launch(headless=True)
                scraper.context = await scraper.browser.new_context()
                
                offices = await scraper.scrape_agents_page()
                
                await scraper.context.close()
                await scraper.browser.close()
            
            print(f"✓ Found {len(offices)} offices")
            
            if offices:
                print("\nFirst 3 offices:")
                for i, office in enumerate(offices[:3], 1):
                    print(f"\n{i}. {office['name']}")
                    print(f"   URL: {office['url']}")
                    print(f"   Phone: {office['telephone']}")
                    print(f"   Email: {office['email']}")
        except Exception as e:
            print(f"✗ Error: {e}")
            return
    
    # Test 2: Scrape one office's listings
    if offices:
        print("\n" + "="*80)
        print("Test 2: Scraping listings from first office")
        print("-" * 80)
        
        test_office = offices[0]
        print(f"Office: {test_office['name']}")
        print(f"URL: {test_office['url']}")
        
        # Try yesterday and today
        for days_back in [1, 0]:
            filter_date = datetime.now() - timedelta(days=days_back)
            filter_date_str = filter_date.strftime('%Y-%m-%d')
            
            print(f"\nTrying date: {filter_date_str}")
            
            async with asyncio.timeout(60):
                try:
                    from playwright.async_api import async_playwright
                    async with async_playwright() as p:
                        scraper.browser = await p.chromium.launch(headless=True)
                        scraper.context = await scraper.browser.new_context()
                        
                        listings = await scraper.scrape_office_listings(
                            test_office['url'], 
                            filter_date_str
                        )
                        
                        await scraper.context.close()
                        await scraper.browser.close()
                    
                    print(f"  ✓ Found {len(listings)} listings")
                    
                    if listings:
                        print(f"\n  First listing:")
                        listing = listings[0]
                        print(f"    Name: {listing['name']}")
                        print(f"    URL: {listing['url']}")
                        print(f"    Price: {listing['price']}")
                        print(f"    Region: {listing['addressRegion']}")
                        print(f"    Locality: {listing['addressLocality']}")
                        
                        # Test 3: Get view count
                        print("\n" + "="*80)
                        print("Test 3: Getting view count for first listing")
                        print("-" * 80)
                        
                        async with asyncio.timeout(30):
                            try:
                                from playwright.async_api import async_playwright
                                async with async_playwright() as p:
                                    scraper.browser = await p.chromium.launch(headless=True)
                                    scraper.context = await scraper.browser.new_context()
                                    
                                    views = await scraper.scrape_listing_views(listing['url'])
                                    
                                    await scraper.context.close()
                                    await scraper.browser.close()
                                
                                if views is not None:
                                    print(f"✓ Views: {views}")
                                else:
                                    print("⚠ Could not extract view count")
                            except Exception as e:
                                print(f"✗ Error: {e}")
                        
                        # Test 4: Generate Excel
                        print("\n" + "="*80)
                        print("Test 4: Generating Excel file")
                        print("-" * 80)
                        
                        test_office['listings'] = listings[:3]  # Just first 3 listings
                        
                        try:
                            os.makedirs('debug_output', exist_ok=True)
                            
                            # Create info sheet with columns as headers
                            info_data = {
                                'Name': [test_office.get('name', '')],
                                'URL': [test_office.get('url', '')],
                                'Description': [test_office.get('description', '')],
                                'Telephone': [test_office.get('telephone', '')],
                                'Email': [test_office.get('email', '')],
                                'Image': [test_office.get('image', '')],
                                'Instagram': [test_office.get('instagram', '')],
                                'Website': [test_office.get('website', '')]
                            }
                            df_info = pd.DataFrame(info_data)
                            
                            # Create main sheet
                            main_data = []
                            for listing in test_office['listings']:
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
                                    'Relative Date': calculate_relative_date(date_published)
                                })
                            df_main = pd.DataFrame(main_data)
                            
                            # Save to Excel
                            excel_path = 'debug_output/test_office.xlsx'
                            with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
                                df_info.to_excel(writer, sheet_name='info', index=False)
                                df_main.to_excel(writer, sheet_name='main', index=False)
                            
                            print(f"✓ Excel file created: {excel_path}")
                        except Exception as e:
                            print(f"✗ Error: {e}")
                        
                        break  # Found listings, no need to try other dates
                    
                except Exception as e:
                    print(f"  ✗ Error: {e}")
    
    print("\n" + "="*80)
    print("DEBUG TEST COMPLETED")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_scraper())
