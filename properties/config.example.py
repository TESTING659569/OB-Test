# Configuration file for Boshamlan Scraper
# Copy this file to config.py and update with your values

# AWS Configuration
AWS_ACCESS_KEY_ID = 'your-access-key-id-here'
AWS_SECRET_ACCESS_KEY = 'your-secret-access-key-here'
AWS_REGION = 'us-east-1'  # Change if needed

# S3 Configuration
S3_BUCKET_NAME = 'data-collection-dl'
S3_BASE_PATH = 'boshamlan-data/properties'

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
