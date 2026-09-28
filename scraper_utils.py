"""
Utility functions for web scraping with human-like behavior.
Provides random delays and user-agent rotation to avoid detection.
"""

import random
import asyncio


# List of realistic user agents from various browsers and platforms
USER_AGENTS = [
    # Chrome on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    
    # Chrome on Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    
    # Firefox on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    
    # Firefox on Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
    
    # Safari on Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    
    # Edge on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    
    # Chrome on Linux
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    
    # Mobile Safari (iPhone)
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
    
    # Mobile Chrome (Android)
    'Mozilla/5.0 (Linux; Android 13; SM-S901U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
]


def get_random_user_agent():
    """
    Get a random user agent string from the list.
    
    Returns:
        str: A random user agent string
    """
    return random.choice(USER_AGENTS)


def get_random_headers():
    """
    Generate random HTTP headers that mimic a real browser.
    
    Returns:
        dict: Dictionary of HTTP headers
    """
    user_agent = get_random_user_agent()
    
    # Common headers that browsers send
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': random.choice([
            'en-US,en;q=0.9',
            'en-US,en;q=0.9,ar;q=0.8',
            'ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7',
            'en-GB,en;q=0.9',
        ]),
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': random.choice(['1', '0']),  # Do Not Track
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': random.choice(['none', 'same-origin', 'cross-site']),
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    return headers


async def random_delay(min_seconds=1.0, max_seconds=3.0):
    """
    Add a random delay to simulate human behavior.
    
    Args:
        min_seconds (float): Minimum delay in seconds
        max_seconds (float): Maximum delay in seconds
    """
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def random_short_delay(min_seconds=0.3, max_seconds=1.0):
    """
    Add a short random delay for quick interactions.
    
    Args:
        min_seconds (float): Minimum delay in seconds
        max_seconds (float): Maximum delay in seconds
    """
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def random_long_delay(min_seconds=2.0, max_seconds=5.0):
    """
    Add a longer random delay for page transitions or heavy loads.
    
    Args:
        min_seconds (float): Minimum delay in seconds
        max_seconds (float): Maximum delay in seconds
    """
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def random_page_load_delay(min_seconds=1.5, max_seconds=3.5):
    """
    Add a random delay simulating page load thinking time.
    
    Args:
        min_seconds (float): Minimum delay in seconds
        max_seconds (float): Maximum delay in seconds
    """
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


def get_playwright_context_args():
    """
    Get context arguments for Playwright with random user agent and headers.
    
    Returns:
        dict: Dictionary of context arguments for Playwright
    """
    user_agent = get_random_user_agent()
    
    # Randomize viewport size slightly
    viewport_width = random.choice([1920, 1366, 1440, 1536, 1280])
    viewport_height = random.choice([1080, 768, 900, 864, 720])
    
    context_args = {
        'user_agent': user_agent,
        'viewport': {'width': viewport_width, 'height': viewport_height},
        'locale': random.choice(['en-US', 'en-GB', 'ar-SA']),
        'timezone_id': random.choice(['America/New_York', 'Europe/London', 'Asia/Riyadh', 'America/Los_Angeles']),
        'extra_http_headers': {
            'Accept-Language': random.choice([
                'en-US,en;q=0.9',
                'en-US,en;q=0.9,ar;q=0.8',
                'ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7',
            ]),
            'DNT': random.choice(['1', '0']),
        }
    }
    
    return context_args
