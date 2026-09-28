# Configuration file for Boshamlan Scraper (Cloudflare R2)
# Copy this file to config.py and update with your values

# Cloudflare R2 Configuration
CF_R2_ACCESS_KEY_ID = 'your-r2-access-key-id-here'
CF_R2_SECRET_ACCESS_KEY = 'your-r2-secret-access-key-here'
CF_R2_ENDPOINT_URL = 'https://<account_id>.r2.cloudflarestorage.com'

# R2 Configuration
R2_BUCKET_NAME = 'data-collection-dl'
R2_BASE_PATH = 'boshamlan-data/properties'

# Scraper Configuration
SCRAPER_OUTPUT_DIR = 'scraped_data'

# Categories and Subcategories Configuration
# You can modify these if the website structure changes
CATEGORIES = {
    'rent': {
        'c_param': 1,
        'subcategories': {
            'عقارات': 1,
            'شقة': 2,
            'منزل': 3,
            'دور': 4,
            'فيلا': 5,
            'شاليه': 6,
            'أرض': 7,
            'مكتب': 8,
            'محل': 9,
            'مخزن': 10,
            'مزرعة': 11,
            'عمارة': 12
        }
    },
    'sale': {
        'c_param': 2,
        'subcategories': {
            'عقارات': 1,
            'شقة': 2,
            'منزل': 3,
            'دور': 4,
            'فيلا': 5,
            'شاليه': 6,
            'أرض': 7,
            'مكتب': 8,
            'محل': 9,
            'مخزن': 10,
            'مزرعة': 11,
            'عمارة': 12
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
