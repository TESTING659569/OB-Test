import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PropertyCardScraper import PropertyCardScraper


async def debug_scraper():
    """
    Debug script to identify correct selectors for the website.
    This will save a screenshot and HTML file for inspection.
    """
    # Test URL - rent -> عقارات
    test_url = "https://www.boshamlan.com/search?c=1&t=1"
    
    print("="*70)
    print("DEBUG MODE - Testing Scraper")
    print("="*70)
    print(f"URL: {test_url}")
    print()
    
    scraper = PropertyCardScraper(test_url, debug=True)
    result = await scraper.scrape_cards()
    
    print()
    print("="*70)
    print("RESULT:")
    print("="*70)
    print(result)
    print()
    
    print("Check these files for debugging:")
    print("  - debug_screenshot.png (screenshot of the page)")
    print("  - debug_page.html (full HTML of the page)")
    print()
    print("To find the correct selector:")
    print("  1. Open debug_screenshot.png to see what the page looks like")
    print("  2. Open debug_page.html in a browser")
    print("  3. Right-click on a property card and select 'Inspect'")
    print("  4. Look at the HTML structure and classes used")
    print("  5. Update the selector in PropertyCardScraper.py")
    print()


if __name__ == "__main__":
    asyncio.run(debug_scraper())
