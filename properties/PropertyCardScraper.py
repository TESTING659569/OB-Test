import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime, timedelta
import aiohttp
import sys
import os

# Add parent directory to path to import scraper_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_utils import (
    random_delay, 
    random_short_delay, 
    random_long_delay,
    random_page_load_delay, 
    get_playwright_context_args,
    get_random_headers
)


class PropertyCardScraper:
    def __init__(self, url):
        self.url = url
        self.browser = None
        self.context = None

    async def scrape_cards(self, max_retries=2):
        async with async_playwright() as p:
            self.browser = await p.chromium.launch(headless=True)
            # Use random user-agent and browser settings
            context_args = get_playwright_context_args()
            self.context = await self.browser.new_context(**context_args)
            main_page = await self.context.new_page()

            try:
                print(f"Navigating to {self.url}...")
                await main_page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
                
                # Random page load delay (1.5-3.5 seconds)
                await random_page_load_delay()
                
                # Try multiple possible selectors
                possible_selectors = [
                    'article',  # Main card container (found via inspection)
                    '.relative.min-h-48',  # Original selector (fallback)
                    '[class*="card"]',  # Any class containing "card"
                    '[class*="property"]',  # Any class containing "property"
                    '.grid > div',  # Grid items
                    'a[href*="/property/"]',  # Links to properties
                    'div[class*="listing"]',  # Listing containers
                ]
                
                cards_selector = None
                for selector in possible_selectors:
                    try:
                        elements = await main_page.query_selector_all(selector)
                        if len(elements) > 0:
                            print(f"✓ Found {len(elements)} elements with selector: {selector}")
                            cards_selector = selector
                            break
                    except:
                        continue
                
                if not cards_selector:
                    print("ERROR: Could not find any cards with known selectors")
                    print("Available classes on page:")
                    # Get all unique classes on the page
                    all_classes = await main_page.evaluate('''
                        () => {
                            const classes = new Set();
                            document.querySelectorAll('*').forEach(el => {
                                el.classList.forEach(cls => classes.add(cls));
                            });
                            return Array.from(classes).slice(0, 50);
                        }
                    ''')
                    print(f"Sample classes: {', '.join(all_classes[:20])}")
                    return "No cards found on this page."
                
                # Scroll to load all posts
                await self.scroll_to_bottom(main_page)

                # Get all card containers with the found selector
                posts = await main_page.query_selector_all(cards_selector)

                if not posts:
                    print("No card containers found on page")
                    return "No cards found on this page."

                print(f"Found {len(posts)} cards on page")
                result = []
                for index, post in enumerate(posts):
                    print(f"Processing card {index + 1}/{len(posts)}...")

                    # Get post ID and fetch data from API
                    post_id = await post.get_attribute('data-post-id')
                    
                    if post_id:
                        # Fetch all data from API endpoint
                        api_data = await self.fetch_from_api(post_id)
                        
                        if api_data:
                            # Build full URL from slug and append post_id
                            link = f"https://www.boshamlan.com{api_data.get('slug', '')}/{post_id}" if api_data.get('slug') else None
                            
                            # Check if property is featured (مميز)
                            is_featured = await self.check_if_featured(post)
                            
                            # Get published date from time element
                            date_published = await self.scrape_datetime(post)
                            
                            card_data = {
                                'title': api_data.get('title_ar'),
                                'price': str(api_data.get('price', '')) if api_data.get('price') else None,
                                'relative_date': await self.scrape_text(post, 'time span'),  # Still from HTML
                                'date_published': date_published,
                                'is_featured': is_featured,
                                'description': api_data.get('description_ar'),
                                'image_url': api_data.get('images', [{}])[0].get('path') if api_data.get('images') else None,
                                'link': link,
                                'mobile_number': api_data.get('contact'),
                                'views_number': str(api_data.get('views', '')) if api_data.get('views') else None
                            }
                            
                            result.append(card_data)
                        else:
                            print(f"  Failed to fetch API data for post {post_id}")
                    else:
                        print(f"  No post_id found for card {index + 1}")

                # Filter cards based on relative_date format "any number ساعة"
                print(f"\nSample data before filtering (first 3 cards):")
                for i, card in enumerate(result[:3]):
                    print(f"Card {i+1}:")
                    title = card.get('title') or 'N/A'
                    print(f"  Title: {title[:50] if len(title) > 50 else title}")
                    print(f"  Price: {card.get('price') or 'N/A'}")
                    print(f"  Relative Date: {card.get('relative_date') or 'N/A'}")
                    print(f"  Link: {card.get('link') or 'N/A'}")
                
                result = self.filter_by_relative_date(result)
                
                print(f"\nAfter filtering: {len(result)} cards remain")
                return json.dumps(result, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"ERROR in scrape_cards: {type(e).__name__}: {e}")
                return "No cards found on this page."
            finally:
                await self.browser.close()

    def filter_by_relative_date(self, cards):
        """
        Filters the cards based on date_published (yesterday or today only).
        """
        from datetime import datetime, timezone
        
        filtered_cards = []
        now = datetime.now(timezone.utc)
        # Get yesterday's date at 00:00:00
        yesterday_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=1)
        
        for card in cards:
            date_published = card.get('date_published')
            
            if date_published:
                try:
                    # Parse ISO datetime string (e.g., "2026-01-08T22:52:53+03:00")
                    published_dt = datetime.fromisoformat(date_published.replace('+03:00', '+00:00'))
                    
                    # Keep cards from yesterday onwards (yesterday or today)
                    if published_dt >= yesterday_start:
                        filtered_cards.append(card)
                except Exception as e:
                    # If parsing fails, skip this card
                    print(f"Failed to parse date_published '{date_published}': {e}")
                    continue
        
        return filtered_cards

    async def scrape_text(self, post, selector):
        try:
            element = await post.query_selector(selector)
            if element:
                return await element.text_content()
        except Exception as e:
            print(f"Failed to scrape {selector}: {e}")
        return None
    
    async def check_if_featured(self, post):
        """
        Check if the property has the 'مميز' (featured) tag.
        
        Returns:
            True if featured, False otherwise
        """
        try:
            # Look for the featured tag element containing 'مميز'
            featured_element = await post.query_selector('div.absolute.bg-\(--sticky-tag\)')
            if featured_element:
                text = await featured_element.text_content()
                if text and 'مميز' in text.strip():
                    return True
        except Exception as e:
            # Silently fail, not critical
            pass
        return False
    
    async def scrape_datetime(self, post):
        """
        Scrape the datetime attribute from the time element.
        
        Returns:
            ISO datetime string or None
        """
        try:
            # Try multiple selectors for the time element
            time_element = await post.query_selector('time[datetime]')
            if not time_element:
                time_element = await post.query_selector('time')
            
            if time_element:
                datetime_value = await time_element.get_attribute('datetime')
                if datetime_value:
                    return datetime_value
        except Exception as e:
            print(f"Failed to scrape datetime: {e}")
        return None

    async def scrape_description(self, post):
        try:
            description_element = await post.query_selector('p.text-sm.line-clamp-2')
            if description_element:
                return await description_element.text_content()
        except Exception as e:
            print(f"Failed to scrape description: {e}")
        return None

    async def scrape_image(self, post):
        try:
            # Images are in the first div with flex-shrink-0
            img_element = await post.query_selector('img')
            if img_element:
                return await img_element.get_attribute('src')
        except Exception as e:
            print(f"Failed to scrape image: {e}")
        return None

    async def fetch_from_api(self, post_id):
        """
        Fetch property data from the API endpoint.
        API URL: https://api.boshamlan.com/api/listings/{post_id}
        Returns: dict with keys like slug, title_ar, description_ar, price, views, contact, images
        """
        try:
            api_url = f"https://api.boshamlan.com/api/listings/{post_id}"
            
            # Get random headers for the request
            headers = get_random_headers()
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        # The actual data is in data['data']
                        return data.get('data', {})
                    else:
                        print(f"  API returned status {response.status} for post {post_id}")
                        return None
        except Exception as e:
            print(f"  API error for post {post_id}: {e}")
            return None

    async def scrape_link_from_article(self, post):
        """
        Get the property link using JavaScript click and route listener.
        """
        new_page = None
        try:
            # Get the post ID from the current card
            post_id = await post.get_attribute('data-post-id')
            if not post_id:
                print("  No data-post-id found")
                return None
            
            # Create a new page and navigate to the search URL
            new_page = await self.context.new_page()
            
            # Set up a route listener to capture navigation
            captured_url = {'url': None}
            
            async def route_handler(route):
                # Capture the URL being navigated to
                url = route.request.url
                if post_id in url:
                    captured_url['url'] = url
                await route.continue_()
            
            # Listen for all navigation requests
            await new_page.route('**/*', route_handler)
            
            await new_page.goto(self.url, wait_until='load')
            
            # Random delay for JavaScript and Svelte to be ready (2-4 seconds)
            await random_delay(2.0, 4.0)
            
            # Wait for cards to load
            await new_page.wait_for_selector('article[data-post-id]', timeout=10000)
            
            # Find the card with matching post-id
            card_selector = f'article[data-post-id="{post_id}"]'
            matching_card = await new_page.wait_for_selector(card_selector, timeout=10000)
            
            if matching_card:
                # Store initial URL
                initial_url = new_page.url
                
                # Scroll card into view
                await matching_card.scroll_into_view_if_needed()
                # Random short delay (0.3-0.8 seconds)
                await random_short_delay(0.3, 0.8)
                
                # Try JavaScript click first
                await new_page.evaluate(f'''() => {{
                    const card = document.querySelector('article[data-post-id="{post_id}"]');
                    if (card) {{
                        card.click();
                    }}
                }}''')
                
                # Wait for URL change
                for i in range(50):  # 5 seconds
                    # Random tiny delay (0.08-0.15 seconds)
                    await random_short_delay(0.08, 0.15)
                    current_url = new_page.url
                    
                    # Check if URL changed
                    if current_url != initial_url:
                        print(f"  Got URL: {current_url}")
                        await new_page.close()
                        return current_url
                    
                    # Check if we captured it via route
                    if captured_url['url']:
                        print(f"  Got URL from route: {captured_url['url']}")
                        await new_page.close()
                        return captured_url['url']
                
                print(f"  URL didn't change after clicking")
            
            await new_page.close()
            return None

        except Exception as e:
            print(f"  Failed to scrape link: {e}")
            if new_page:
                try:
                    await new_page.close()
                except:
                    pass
            return None

    # No longer needed - data comes from API
    # async def scrape_link_from_article(self, post):
    # async def scrape_mobile_number(self, link, page):
    # async def scrape_views_number(self, link, page):

    async def scroll_to_bottom(self, page):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        button_selector = (
            'button.text-base.shrink-0.select-none.whitespace-nowrap.transition-colors.'
            'disabled\\:opacity-50.h-12.font-bold.bg-primary.text-on-primary.active\\:bg-active-primary.'
            'w-full.cursor-pointer.z-20.max-w-2xl.py-3.md\\:py-4.px-8.rounded-full.flex.items-center.justify-center.gap-2\\.5'
        )

        # 1. Press the button ONCE if found
        try:
            button = await page.query_selector(button_selector)
            if button:
                is_disabled = await button.get_property('disabled')
                if not is_disabled:
                    await button.click()
                    # Random long delay for items to load (8-12 seconds)
                    await random_long_delay(8.0, 12.0)
        except Exception as e:
            print(f"Could not click 'Show More' button: {e}")

        # 2. Begin scrolling and checking card dates
        consecutive_old = 0
        previous_height = 0
        no_new_content_count = 0
        max_scrolls = 50  # Safety limit
        scroll_count = 0
        
        while scroll_count < max_scrolls:
            # Get current scroll height before scrolling
            current_height = await page.evaluate('document.body.scrollHeight')
            
            # Scroll to bottom
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            # Random delay for content to load (2.5-4.0 seconds)
            await random_delay(2.5, 4.0)
            
            # Get new height after scrolling
            new_height = await page.evaluate('document.body.scrollHeight')
            
            # Check if page height didn't change (reached actual bottom)
            if new_height == previous_height:
                no_new_content_count += 1
                if no_new_content_count >= 3:  # No new content after 3 attempts
                    print("Reached end of page (no new content loading).")
                    break
            else:
                no_new_content_count = 0
            
            previous_height = new_height

            # Get all relative date elements
            date_elements = await page.query_selector_all('.rounded.text-xs.flex.items-center.gap-1')
            date_texts = []
            for elem in date_elements:
                txt = await elem.text_content()
                if txt:
                    date_texts.append(txt.strip())

            # Check only the LAST 10 cards for stopping condition
            recent_dates = date_texts[-10:] if len(date_texts) >= 10 else date_texts
            
            consecutive_old = 0
            for date_str in recent_dates:
                try:
                    card_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if card_date < datetime.strptime(yesterday, "%Y-%m-%d"):
                        consecutive_old += 1
                    else:
                        consecutive_old = 0
                except ValueError:
                    # Check if it's a fresh card (hours, minutes, or 1 day)
                    if any(word in date_str for word in ['ساعة', 'دقيقة']):
                        consecutive_old = 0  # Reset, it's a fresh card
                    elif '1 يوم' in date_str:
                        consecutive_old = 0  # 1 day is still fresh
                    else:
                        consecutive_old += 1
            
            # Stop if we found 5 consecutive old cards in the recent batch
            if consecutive_old >= 5:
                print(f"5 consecutive old cards found in last {len(recent_dates)} cards. Stopping scroll.")
                break
            
            scroll_count += 1
        
        if scroll_count >= max_scrolls:
            print(f"Reached maximum scroll limit ({max_scrolls} scrolls).")

