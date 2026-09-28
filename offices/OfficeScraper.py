import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
import sys
import os

# Add parent directory to path to import scraper_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import random_delay, random_short_delay, random_page_load_delay, get_playwright_context_args


class OfficeScraper:
    """
    Scrapes office data from boshamlan.com/agents and their listings.
    Extracts office information, listings, and view counts.
    """
    
    def __init__(self):
        self.base_url = "https://www.boshamlan.com"
        self.agents_url = f"{self.base_url}/agents"
        self.browser = None
        self.context = None
    
    async def scrape_all_offices(self, filter_date=None):
        """
        Scrape all offices and their listings.
        
        Args:
            filter_date: Date to filter listings (default: yesterday)
            
        Returns:
            List of office dictionaries with info and listings
        """
        if filter_date is None:
            filter_date = datetime.now() - timedelta(days=1)
        
        filter_date_str = filter_date.strftime('%Y-%m-%d')
        print(f"Filtering listings from date: {filter_date_str}")
        
        async with async_playwright() as p:
            self.browser = await p.chromium.launch(headless=True)
            # Use random user-agent and browser settings
            context_args = get_playwright_context_args()
            self.context = await self.browser.new_context(**context_args)
            
            try:
                # Step 1: Get all offices from main agents page
                offices_data = await self.scrape_agents_page()
                print(f"Found {len(offices_data)} offices")
                
                # Step 2: For each office, get their listings
                all_offices = []
                for idx, office in enumerate(offices_data, 1):
                    print(f"\n[{idx}/{len(offices_data)}] Processing office: {office['name']}")
                    
                    # Get listings for this office
                    listings, number_of_items = await self.scrape_office_listings(office['url'], filter_date_str)
                    
                    # Always add office, even if no listings from filter date
                    office['ads_number'] = number_of_items
                    
                    if listings:
                        print(f"  Found {len(listings)} listings from {filter_date_str}")
                        
                        # Step 3: Get view counts for each listing
                        for listing_idx, listing in enumerate(listings, 1):
                            print(f"  Getting views for listing {listing_idx}/{len(listings)}: {listing['name'][:50]}...")
                            views = await self.scrape_listing_views(listing['url'])
                            listing['views'] = views
                            # Random delay between 0.5 to 1.5 seconds
                            await random_short_delay(0.5, 1.5)
                        
                        office['listings'] = listings
                    else:
                        print(f"  No listings found from {filter_date_str}")
                        office['listings'] = []  # Empty listings list
                    
                    all_offices.append(office)
                    
                    # Random delay between offices (1-3 seconds)
                    await random_delay(1.0, 3.0)
                
                return all_offices
                
            finally:
                await self.context.close()
                await self.browser.close()
    
    async def scrape_agents_page(self):
        """
        Scrape the main agents page to get all offices.
        Extracts JSON-LD data from the page.
        
        Returns:
            List of office dictionaries
        """
        page = await self.context.new_page()
        
        try:
            print(f"Loading agents page: {self.agents_url}")
            await page.goto(self.agents_url, wait_until='domcontentloaded', timeout=30000)
            # Random page load delay (1.5-3.5 seconds)
            await random_page_load_delay()
            
            # Get page content
            content = await page.content()
            
            # Parse JSON-LD data
            offices = self._extract_offices_from_html(content)
            
            return offices
            
        finally:
            await page.close()
    
    def _extract_offices_from_html(self, html_content):
        """
        Extract office data from JSON-LD in HTML.
        
        Args:
            html_content: HTML content of the page
            
        Returns:
            List of office dictionaries
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        offices = []
        
        # Find all script tags with type="application/ld+json"
        scripts = soup.find_all('script', type='application/ld+json')
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                
                # Handle @graph structure
                if '@graph' in data:
                    for item in data['@graph']:
                        if item.get('@type') == 'ItemList' and 'itemListElement' in item:
                            # This is the offices list
                            for element in item['itemListElement']:
                                if element.get('@type') == 'ListItem':
                                    office_item = element.get('item', {})
                                    if office_item.get('@type') == 'RealEstateAgent':
                                        office_data = self._parse_office_data(office_item)
                                        offices.append(office_data)
                elif data.get('@type') == 'ItemList' and 'itemListElement' in data:
                    # Direct ItemList structure
                    for element in data['itemListElement']:
                        if element.get('@type') == 'ListItem':
                            office_item = element.get('item', {})
                            if office_item.get('@type') == 'RealEstateAgent':
                                office_data = self._parse_office_data(office_item)
                                offices.append(office_data)
            except json.JSONDecodeError:
                continue
        
        return offices
    
    def _parse_office_data(self, office_item):
        """
        Parse office data from JSON-LD item.
        
        Args:
            office_item: Office data from JSON-LD
            
        Returns:
            Dictionary with office information
        """
        contact_point = office_item.get('contactPoint', [{}])[0] if office_item.get('contactPoint') else {}
        
        office_data = {
            'url': office_item.get('url', ''),
            'name': office_item.get('name', ''),
            'description': office_item.get('description', ''),
            'image': office_item.get('image', ''),
            'telephone': contact_point.get('telephone', ''),
            'email': contact_point.get('email', ''),
            'instagram': '',
            'website': ''
        }
        
        # Extract social media links
        same_as = office_item.get('sameAs', [])
        for link in same_as:
            if 'instagram.com' in link:
                office_data['instagram'] = link
            elif link and 'boshamlan.com' not in link:
                office_data['website'] = link
        
        return office_data
    
    async def scrape_office_listings(self, office_url, filter_date_str):
        """
        Scrape listings from an office page.
        
        Args:
            office_url: URL of the office page
            filter_date_str: Date string to filter listings (YYYY-MM-DD)
            
        Returns:
            List of listing dictionaries
        """
        page = await self.context.new_page()
        
        try:
            print(f"  Loading office page: {office_url}")
            await page.goto(office_url, wait_until='domcontentloaded', timeout=30000)
            # Random page load delay (1.5-3.5 seconds)
            await random_page_load_delay()
            
            # Get page content
            content = await page.content()
            
            # Parse JSON-LD data
            listings, number_of_items = self._extract_listings_from_html(content, filter_date_str)
            
            return listings, number_of_items
            
        finally:
            await page.close()
    
    def _extract_listings_from_html(self, html_content, filter_date_str):
        """
        Extract listing data from JSON-LD in HTML.
        Filters listings by date.
        
        Args:
            html_content: HTML content of the page
            filter_date_str: Date string to filter listings (YYYY-MM-DD)
            
        Returns:
            Tuple of (list of listing dictionaries, total number of items)
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        number_of_items = 0
        
        # Find all script tags with type="application/ld+json"
        scripts = soup.find_all('script', type='application/ld+json')
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                
                # Handle @graph structure
                if '@graph' in data:
                    for item in data['@graph']:
                        if item.get('@type') == 'ItemList' and 'itemListElement' in item:
                            # This is the listings list
                            number_of_items = item.get('numberOfItems', 0)
                            for element in item['itemListElement']:
                                listing_data = self._parse_listing_data(element, filter_date_str)
                                if listing_data:
                                    listings.append(listing_data)
                elif data.get('@type') == 'ItemList' and 'itemListElement' in data:
                    # Direct ItemList structure
                    number_of_items = data.get('numberOfItems', 0)
                    for element in data['itemListElement']:
                        listing_data = self._parse_listing_data(element, filter_date_str)
                        if listing_data:
                            listings.append(listing_data)
            except json.JSONDecodeError:
                continue
        
        return listings, number_of_items
    
    def _parse_listing_data(self, listing_element, filter_date_str):
        """
        Parse listing data from JSON-LD element.
        Filters by date (yesterday onwards).
        
        Args:
            listing_element: Listing element from JSON-LD
            filter_date_str: Date string to filter listings (YYYY-MM-DD) - represents yesterday
            
        Returns:
            Dictionary with listing information or None if filtered out
        """
        if listing_element.get('@type') != 'RealEstateListing':
            return None
        
        # Get the date published
        date_published = listing_element.get('datePublished', '')
        
        # Parse the date (format: "2026-01-05T22:57:43+03:00")
        if date_published:
            try:
                # Parse the ISO datetime
                from datetime import datetime, timezone
                published_dt = datetime.fromisoformat(date_published.replace('+03:00', '+00:00'))
                
                # Parse filter date (yesterday at 00:00:00)
                filter_dt = datetime.fromisoformat(filter_date_str + 'T00:00:00+00:00')
                
                # Filter: keep only listings from yesterday onwards
                if published_dt < filter_dt:
                    return None
            except Exception as e:
                print(f"    Failed to parse date '{date_published}': {e}")
                return None
        else:
            return None
        
        # Extract address information
        about = listing_element.get('about', {})
        address = about.get('address', {})
        
        # Extract price from offers
        offers = listing_element.get('offers', {})
        price = offers.get('price', '')
        
        # Extract image
        image_obj = listing_element.get('image', {})
        image_url = image_obj.get('url', '') if isinstance(image_obj, dict) else ''
        
        listing_data = {
            'name': listing_element.get('name', ''),
            'url': listing_element.get('url', ''),
            'description': listing_element.get('description', ''),
            'image_url': image_url,
            'price': price,
            'addressRegion': address.get('addressRegion', ''),
            'addressLocality': address.get('addressLocality', ''),
            'datePublished': date_published,
            'views': None  # Will be filled later
        }
        
        return listing_data
    
    async def scrape_listing_views(self, listing_url):
        """
        Scrape view count from a listing detail page.
        
        Args:
            listing_url: URL of the listing detail page
            
        Returns:
            View count as integer or None
        """
        page = await self.context.new_page()
        
        try:
            await page.goto(listing_url, wait_until='domcontentloaded', timeout=30000)
            # Random delay (1.0-2.5 seconds)
            await random_delay(1.0, 2.5)
            
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find the views element
            # The pattern is: <li class="post-info-advertising-details"> with SVG for eye icon and <span> with number
            post_info_items = soup.find_all('li', class_='post-info-advertising-details')
            
            for item in post_info_items:
                # Check if this item contains the eye SVG (viewBox="0 -960 960 960")
                svg = item.find('svg')
                if svg and 'viewBox' in svg.attrs:
                    viewbox = svg['viewBox']
                    # Check for eye icon viewBox
                    if '0 -960 960 960' in viewbox or viewbox == '0 -960 960 960':
                        # This is the views item, get the span text
                        span = item.find('span')
                        if span:
                            views_text = span.text.strip()
                            # Remove any non-digit characters and convert to int
                            views_text = ''.join(filter(str.isdigit, views_text))
                            if views_text:
                                return int(views_text)
            
            # Fallback: try to find any span with numeric content in post-info-advertising-details
            for item in post_info_items:
                span = item.find('span')
                if span:
                    text = span.text.strip()
                    if text.isdigit():
                        return int(text)
            
            return None
            
        except Exception as e:
            print(f"    Error getting views: {e}")
            return None
        finally:
            await page.close()


async def main():
    """Test the scraper"""
    scraper = OfficeScraper()
    
    # Scrape offices with listings from yesterday
    offices = await scraper.scrape_all_offices()
    
    print(f"\n\nTotal offices with listings from yesterday: {len(offices)}")
    for office in offices:
        print(f"\nOffice: {office['name']}")
        print(f"  Listings: {len(office.get('listings', []))}")


if __name__ == "__main__":
    asyncio.run(main())
