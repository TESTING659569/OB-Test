# Properties Scraper - Boshamlan Real Estate Data Collection

A sophisticated asynchronous web scraping system designed to extract real estate property data from Boshamlan.com and upload it to Cloudflare R2 with organized date-based partitioning.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Data Flow](#data-flow)
- [Output Format](#output-format)
- [R2 Storage Structure](#r2-storage-structure)
- [API Integration](#api-integration)
- [Troubleshooting](#troubleshooting)
- [Development & Testing](#development--testing)

---

## 🎯 Overview

This scraper system automates the extraction of property listings from Boshamlan.com, a real estate platform. It scrapes data from multiple categories (rent, sale, exchange) and their subcategories, downloads associated images, and organizes everything in Cloudflare R2 with date-based partitioning for easy data lake management.

**Key Capabilities:**
- Scrapes 3 main categories with 8+ subcategories each
- Filters properties by date (yesterday and today only)
- Downloads and uploads property images to Cloudflare R2
- Creates Excel files with multiple sheets per category
- Implements date-partitioned storage (year/month/day)
- Uses both web scraping and API integration for comprehensive data

---

## ✨ Features

### Data Collection
- **Multi-Category Support**: Rent, Sale, and Exchange properties
- **Sub-Category Filtering**: Apartments, Houses, Land, Commercial, etc.
- **Date-Based Filtering**: Only scrapes recent properties (yesterday/today)
- **Featured Property Detection**: Identifies premium/featured listings
- **Image Extraction**: Downloads all property images
- **API Integration**: Fetches detailed property data from backend API

### Storage & Organization
- **Cloudflare R2 Integration**: Automatic upload to Cloudflare R2 buckets
- **Date Partitioning**: `year=YYYY/month=MM/day=DD` structure
- **Excel Export**: Multi-sheet workbooks per category
- **Image Management**: Organized by category with unique filenames
- **Metadata Tracking**: R2 objects include upload metadata

### Technical Features
- **Asynchronous Operations**: Fast concurrent scraping using asyncio
- **Playwright Automation**: Headless browser for JavaScript rendering
- **Smart Scrolling**: Automatic pagination with stopping conditions
- **Error Handling**: Robust retry mechanisms and error logging
- **Progress Tracking**: Detailed console output with status updates

---

## 🏗️ Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                        main_s3.py                           │
│                   (Orchestrator/Entry Point)                │
└─────────────────┬───────────────────────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
┌──────────────────┐  ┌──────────────────┐
│CategoryScraper.py│  │  S3Uploader.py   │
│  (Coordinator)   │  │  (Cloud Storage) │
└────────┬─────────┘  └──────────────────┘
         │
         ▼
┌─────────────────────┐
│PropertyCardScraper  │
│ (Data Extraction)   │
└─────────────────────┘
```

### Component Details

#### 1. **main_s3.py** - MainS3Scraper
- **Purpose**: Main orchestrator and entry point
- **Responsibilities**:
  - Initialize scrapers and R2 uploader
  - Coordinate scraping workflow
  - Manage image uploads before Excel creation
  - Handle Excel file generation and upload
  - Provide progress reporting

#### 2. **CategoryScraper.py** - CategoryScraper
- **Purpose**: Category-level coordination
- **Responsibilities**:
  - Define category and subcategory structure
  - Build search URLs for each subcategory
  - Coordinate multiple PropertyCardScraper instances
  - Aggregate data from all subcategories
  - Generate Excel files with multiple sheets
  - Store scraped data for image processing

#### 3. **PropertyCardScraper.py** - PropertyCardScraper
- **Purpose**: Low-level web scraping
- **Responsibilities**:
  - Launch Playwright browser sessions
  - Navigate to search pages
  - Detect and locate property cards
  - Extract data from HTML elements
  - Fetch additional data from API endpoints
  - Apply date filters
  - Handle pagination with smart scrolling

#### 4. **S3Uploader.py** - R2 Uploader
- **Purpose**: Cloudflare R2 integration
- **Responsibilities**:
  - Initialize Cloudflare R2 client
  - Upload Excel files with partitioning
  - Download and upload images asynchronously
  - Generate R2 URIs for images
  - Handle Cloudflare R2 credentials
  - Verify bucket accessibility

---

## 📦 Prerequisites

### System Requirements
- Python 3.8 or higher
- 4GB+ RAM recommended
- Stable internet connection
- Cloudflare account with R2 access

### Required Accounts
- **Cloudflare Account**: With R2 bucket access
- **R2 Credentials**: Access key, secret key, and bucket name

---

## 🚀 Installation

### 1. Clone or Navigate to Repository
```bash
cd properties/
```

### 2. Create Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r ../requirements.txt
```

### 4. Install Playwright Browsers
```bash
playwright install chromium
```

**Note**: The scraper uses Playwright for browser automation. The chromium browser (~100MB) must be installed.

---

## ⚙️ Configuration

### Option 1: Environment Variables (Recommended)

**Windows PowerShell:**
```powershell
$env:CLOUDFLARE_R2_ACCESS_KEY_ID="your-access-key"
$env:CLOUDFLARE_R2_SECRET_ACCESS_KEY="your-secret-key"
$env:CLOUDFLARE_R2_ACCOUNT_ID="your-account-id"
$env:CLOUDFLARE_R2_BUCKET_NAME="your-bucket-name"
```

**Linux/Mac Bash:**
```bash
export CLOUDFLARE_R2_ACCESS_KEY_ID="your-access-key"
export CLOUDFLARE_R2_SECRET_ACCESS_KEY="your-secret-key"
export CLOUDFLARE_R2_ACCOUNT_ID="your-account-id"
export CLOUDFLARE_R2_BUCKET_NAME="your-bucket-name"
```

### Option 2: Cloudflare R2 Credentials File
Create/edit `config.py` with your Cloudflare R2 credentials:
```python
CLOUDFLARE_R2_ACCESS_KEY_ID = 'your-access-key'
CLOUDFLARE_R2_SECRET_ACCESS_KEY = 'your-secret-key'
CLOUDFLARE_R2_ACCOUNT_ID = 'your-account-id'
CLOUDFLARE_R2_BUCKET_NAME = 'your-bucket-name'
CLOUDFLARE_R2_ENDPOINT = 'https://<account_id>.r2.cloudflarestorage.com'
```

### R2 Bucket Configuration

**Required Bucket**: your Cloudflare R2 bucket name

**Cloudflare R2 Notes**:
- Use the Cloudflare dashboard to create an R2 bucket.
- Ensure the access key and secret key are enabled for R2 usage.
- If your code uses an endpoint URL, set it to the R2 endpoint for your account.

---

## 🎮 Usage

### Basic Usage

Run the main scraper:
```bash
python main_s3.py
```

### What Happens When You Run It

The scraper executes a **4-step workflow**:

```
Step 1: Check R2 bucket accessibility
  └─ Verifies Cloudflare R2 credentials and bucket permissions

Step 2: Scrape data from all categories
  ├─ Rent (8 subcategories)
  ├─ Sale (8 subcategories)
  └─ Exchange (2 subcategories)

Step 3: Upload images to Cloudflare R2
  └─ Downloads and uploads all property images

Step 4: Create and upload Excel files
  ├─ Generate multi-sheet Excel workbooks
  └─ Upload to Cloudflare R2 with date partitioning
```

### Expected Output

```
================================================================================
BOSHAMLAN SCRAPER - Cloudflare R2 Edition
================================================================================
Started at: 2026-02-22 10:30:45
Target R2: r2://data-collection-dl/boshamlan-data/properties/
  - Excel files -> year=YYYY/month=MM/day=DD/excel files/
  - Images -> year=YYYY/month=MM/day=DD/images/
================================================================================

[1/4] Checking R2 bucket accessibility...
✓ Bucket 'data-collection-dl' exists and is accessible

[2/4] Scraping data from all categories...
######################################################################
# Scraping Category: RENT
######################################################################
Found 150 cards on page
✓ Found 45 items for عقارات
✓ Found 32 items for شقة
... (continues for all subcategories)

[3/4] Uploading images to Cloudflare R2...
✓ Successfully uploaded 245 image(s) to Cloudflare R2

[4/4] Creating and uploading Excel files...
✓ Successfully uploaded 3 Excel file(s) to Cloudflare R2:
  - rent: r2://data-collection-dl/boshamlan-data/properties/year=2026/month=02/day=22/excel files/rent.xlsx
  - sale: r2://data-collection-dl/boshamlan-data/properties/year=2026/month=02/day=22/excel files/sale.xlsx
  - exchange: r2://data-collection-dl/boshamlan-data/properties/year=2026/month=02/day=22/excel files/exchange.xlsx

================================================================================
SCRAPING COMPLETED
================================================================================
Finished at: 2026-02-22 10:45:30
Categories processed: 3
Images uploaded to Cloudflare R2: 245
Excel files uploaded to Cloudflare R2: 3
================================================================================
```

### Advanced Usage

#### Test Single Category
Modify `CategoryScraper.py` to scrape only one category:
```python
# At the bottom of CategoryScraper.py
async def main():
    scraper = CategoryScraper()
    # Scrape only rent category
    await scraper.scrape_category('rent')

asyncio.run(main())
```

#### Local Testing (No R2)
Use the standalone CategoryScraper:
```bash
python CategoryScraper.py
```
This will scrape data and save Excel files locally to `scraped_data/` folder without uploading to R2.

---

## 📁 Project Structure

```
properties/
│
├── main_s3.py                  # Main entry point and orchestrator
├── CategoryScraper.py          # Category-level scraping coordinator
├── PropertyCardScraper.py      # Individual property card scraper
├── S3Uploader.py              # Cloudflare R2 upload handler
│
├── config.example.py          # Example configuration file
├── debug_scraper.py           # Debug tool for selector testing
│
├── README.md                  # This file
└── scraped_data/              # Local output directory (auto-created)
    ├── rent.xlsx              # Generated Excel files
    ├── sale.xlsx
    └── exchange.xlsx
```

### File Descriptions

| File | Lines | Purpose |
|------|-------|---------|
| **main_s3.py** | 173 | Main orchestrator - coordinates entire scraping and upload workflow |
| **CategoryScraper.py** | 262 | Manages categories, builds URLs, coordinates subcategory scraping |
| **PropertyCardScraper.py** | 434 | Core scraper - extracts data from web pages and API |
| **S3Uploader.py** | 354 | Handles all Cloudflare R2 operations (uploads, downloads, partitioning) |
| **debug_scraper.py** | 56 | Debug tool for testing selectors and troubleshooting |
| **config.example.py** | 56 | Template for configuration settings |

---

## 🔄 Data Flow

### Complete Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER RUNS main_s3.py                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
               ┌─────────────────────────┐
               │   Initialize Components  │
               │  - CategoryScraper      │
               │  - R2Uploader           │
               └────────────┬────────────┘
                            │
                            ▼
               ┌─────────────────────────┐
               │  Step 1: Check R2       │
               │  Verify bucket access   │
               └────────────┬────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  Step 2: Scrape All Categories        │
        │  For each category (rent/sale/exchange)│
        └──────────┬─────────────┬──────────────┘
                   │             │
        ┌──────────▼──────┐     └──────────────┐
        │ Build URLs for  │                    │
        │ Subcategories   │                    │
        └──────────┬──────┘                    │
                   │                            │
        ┌──────────▼─────────────┐            │
        │ PropertyCardScraper    │            │
        │ For each subcategory:  │            │
        │  1. Navigate to URL    │            │
        │  2. Find property cards│            │
        │  3. Smart scroll/load  │            │
        │  4. Extract HTML data  │            │
        │  5. Fetch API data     │            │
        │  6. Filter by date     │            │
        └──────────┬───────────── ┘            │
                   │                            │
        ┌──────────▼──────┐                    │
        │ Aggregate Data  │                    │
        │ Store in memory │                    │
        └──────────┬──────┘                    │
                   │                            │
                   └────────────────────────────┘
                                │
                                ▼
        ┌──────────────────────────────────────┐
        │  Step 3: Upload Images to R2         │
        │  For all scraped cards:              │
        │   1. Extract image URLs              │
        │   2. Download images                 │
        │   3. Upload to R2 /images/ folder    │
        │   4. Create URL ↔ R2 URI mapping    │
        └──────────┬───────────────────────────┘
                   │
                   ▼
        ┌──────────────────────────────────────┐
        │  Step 4: Create & Upload Excel       │
        │  For each category:                  │
        │   1. Create Excel with sheets        │
        │   2. Add image_s3_path column        │
        │   3. Save locally                    │
        │   4. Upload to R2 /excel files/      │
        └──────────┬───────────────────────────┘
                   │
                   ▼
        ┌──────────────────────────────────────┐
        │  Final Summary & Cleanup             │
        │  - Display statistics                │
        │  - Report R2 URIs                    │
        └──────────────────────────────────────┘
```

### Step-by-Step Process

1. **Initialization**
   - Load Cloudflare R2 credentials
   - Initialize R2 client
   - Create CategoryScraper instance

2. **R2 Verification**
   - Check bucket existence
   - Verify access permissions
   - Fail fast if credentials invalid

3. **Data Scraping** (Sequential by category)
   - For each main category (rent, sale, exchange):
     - For each subcategory:
       - Build search URL
       - Launch Playwright browser
       - Navigate to search page
       - Find property card containers
       - Scroll to load all matching properties
       - Extract data from HTML elements
       - Fetch additional data from API
       - Filter by date (yesterday/today only)
       - Close browser
     - Aggregate all subcategory data
     - Store in memory for later processing

4. **Image Upload**
   - Extract all unique image URLs
   - Download images asynchronously
   - Generate unique filenames
   - Upload to Cloudflare R2 with date partitioning
   - Create mapping: `original_url → r2://path`

5. **Excel Generation & Upload**
   - For each category:
     - Create Excel workbook
     - Create sheet for each subcategory
     - Add `image_s3_path` column using mapping
     - Save locally to `scraped_data/`
     - Upload to Cloudflare R2 with date partitioning
     - Report R2 URI

---

## 📊 Output Format

### Excel File Structure

Each category produces one Excel file with multiple sheets:

**File**: `rent.xlsx`, `sale.xlsx`, `exchange.xlsx`

**Sheets**: One per subcategory (عقارات, شقة, بيت, أرض, etc.)

### Data Schema

Each row represents one property listing:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `title` | String | Property title in Arabic | "شقة للإيجار 3 غرف" |
| `price` | String | Property price | "2000" |
| `relative_date` | String | Human-readable date | "5 ساعة" |
| `date_published` | ISO DateTime | Exact publication date | "2026-02-22T10:30:00+03:00" |
| `is_featured` | Boolean | Premium listing flag | `True` / `False` |
| `description` | String | Property description | "شقة واسعة ونظيفة..." |
| `image_url` | URL | Original image URL | "https://cdn.boshamlan.com/..." |
| `image_s3_path` | R2 URI | Cloudflare R2 location of image | "r2://bucket/..." |
| `link` | URL | Property detail page | "https://boshamlan.com/property/..." |
| `mobile_number` | String | Contact phone | "+966501234567" |
| `views_number` | String | View count | "150" |

### Sample Data

```csv
title,price,relative_date,date_published,is_featured,description,image_url,image_s3_path,link,mobile_number,views_number
"شقة للإيجار في الرياض","2000","3 ساعة","2026-02-22T07:30:00+03:00",False,"شقة 3 غرف نوم...","https://cdn.boshamlan.com/image1.jpg","r2://data-collection-dl/.../image1.jpg","https://boshamlan.com/property/12345","+966501234567","45"
```

---

## 🗄️ Cloudflare R2 Storage Structure

### Directory Layout

```
r2://data-collection-dl/
└── boshamlan-data/
    └── properties/
        └── year=2026/
            └── month=02/
                └── day=22/
                    ├── excel files/
                    │   ├── rent.xlsx
                    │   ├── sale.xlsx
                    │   └── exchange.xlsx
                    │
                    └── images/
                        ├── rent/
                        │   ├── property_0_20260222_103045.jpg
                        │   ├── property_1_20260222_103046.jpg
                        │   └── ...
                        ├── sale/
                        │   └── ...
                        └── exchange/
                            └── ...
```

### Partitioning Strategy

**Format**: `year=YYYY/month=MM/day=DD`

**Benefits**:
- Efficient querying in data lake architectures
- Easy data lifecycle management
- Cost-effective storage organization
- Compatible with Cloudflare R2 partitioning

### R2 Object Metadata

Each uploaded file includes metadata:

**Excel Files**:
```json
{
  "upload-date": "2026-02-22T10:45:30",
  "category": "rent",
  "source": "boshamlan-scraper",
  "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}
```

**Image Files**:
```json
{
  "upload-date": "2026-02-22T10:40:15",
  "source-url": "https://cdn.boshamlan.com/original/image.jpg",
  "source": "boshamlan-scraper",
  "ContentType": "image/jpeg"
}
```

---

## 🔌 API Integration

### Boshamlan API

The scraper integrates with Boshamlan's backend API for comprehensive data:

**Endpoint**: `https://api-v2.boshamlan.com/api/listings/{post_id}`

**Method**: GET

**Response Structure**:
```json
{
  "data": {
    "slug": "/property/apartment-for-rent-riyadh",
    "title_ar": "شقة للإيجار في الرياض",
    "description_ar": "شقة واسعة ونظيفة...",
    "price": 2000,
    "views": 45,
    "contact": "+966501234567",
    "images": [
      {
        "path": "https://cdn.boshamlan.com/image1.jpg"
      }
    ]
  }
}
```

### Why Hybrid Approach?

The scraper combines **HTML scraping** + **API calls**:

| Data Source | Information Retrieved |
|-------------|----------------------|
| **HTML** | Post IDs, Relative dates, Featured status |
| **API** | Titles, Descriptions, Prices, Images, Contact info, Views |

**Reason**: The API provides cleaner, more structured data, but requires post IDs which must be extracted from the HTML.

---

## 🛠️ Troubleshooting

### Common Issues

#### 1. No Cloudflare R2 Credentials Error

**Symptom**:
```
ERROR: No Cloudflare R2 credentials found
```

**Solution**:
- Set environment variables (see [Configuration](#configuration))
- Or provide credentials in `config.py`
- Verify keys and bucket names are correct

#### 2. R2 Bucket Access Denied

**Symptom**:
```
ERROR: Access denied to bucket 'data-collection-dl'
```

**Solution**:
- Check bucket name is correct
- Verify R2 access keys are enabled
- Check your Cloudflare account permissions
- Ensure the endpoint and account ID are correct

#### 3. No Cards Found

**Symptom**:
```
ERROR: Could not find any cards with known selectors
```

**Solution**:
- Website structure may have changed
- Run `debug_scraper.py` to investigate:
  ```bash
  python debug_scraper.py
  ```
- Check `debug_screenshot.png` and `debug_page.html`
- Update selectors in `PropertyCardScraper.py`

#### 4. Playwright Browser Not Installed

**Symptom**:
```
Executable doesn't exist at /path/to/chromium
```

**Solution**:
```bash
playwright install chromium
```

#### 5. Date Filter Issues

**Symptom**:
```
No data found for all subcategories
```

**Solution**:
- Check if there are any listings from yesterday/today
- Temporarily disable date filter for testing:
  ```python
  # In PropertyCardScraper.py, comment out:
  # result = self.filter_by_relative_date(result)
  ```

#### 6. Memory Issues

**Symptom**:
```
MemoryError or slow performance
```

**Solution**:
- Reduce concurrent operations
- Process categories one at a time
- Close browser sessions promptly
- Increase system RAM

### Debug Mode

Enable detailed logging by running the debug scraper:

```bash
python debug_scraper.py
```

This will:
- Save `debug_screenshot.png` - Visual capture of the page
- Save `debug_page.html` - Full HTML for inspection
- Print all discovered selectors
- Show sample data extraction

---

## 🧪 Development & Testing

### Running Tests

#### Test Single URL
```python
# In PropertyCardScraper.py
async def test():
    scraper = PropertyCardScraper("https://www.boshamlan.com/search?c=1&t=1")
    result = await scraper.scrape_cards()
    print(result)

asyncio.run(test())
```

#### Test Without R2
```bash
# Run CategoryScraper independently
python CategoryScraper.py
```
Saves Excel files locally to `scraped_data/` without R2 upload.

#### Test R2 Upload Only
```python
# In S3Uploader.py
uploader = S3Uploader()
print(uploader.check_bucket_exists())
```

### Modifying Selectors

If the website structure changes, update selectors in `PropertyCardScraper.py`:

```python
# Line 30-40: Card container selectors
possible_selectors = [
    'article',                    # Add new selectors here
    '.relative.min-h-48',
    '[class*="card"]',
    # ... add more
]
```

### Adding New Categories

Edit `CategoryScraper.py`:

```python
self.categories = {
    'new_category': {
        'c_param': 4,  # New category parameter
        'subcategories': {
            'فئة جديدة': 1,
            'فئة ثانية': 2
        }
    }
}
```

### Custom Date Range

Modify `PropertyCardScraper.filter_by_relative_date()`:

```python
# Change from yesterday to last 7 days
days_back = 7
cutoff_date = datetime.now() - timedelta(days=days_back)
```

---

## 📈 Performance Metrics

### Typical Execution

- **Total Runtime**: 10-15 minutes
- **Properties Scraped**: 150-300 items
- **Images Uploaded**: 150-300 images
- **Excel Files Created**: 3 files
- **R2 Uploads**: ~300 objects total

### Resource Usage

- **Memory**: 300-500 MB peak
- **Network**: 50-200 MB download (images)
- **Disk**: 10-50 MB temporary (deleted after upload)

---

## 📝 Notes

1. **Rate Limiting**: The scraper includes deliberate delays (2-3 seconds) between requests to be respectful to the target website.

2. **Data Freshness**: Only scrapes properties published yesterday or today. Older listings are filtered out.

3. **Featured Detection**: Identifies premium "مميز" listings with special flag.

4. **Image Handling**: Images are downloaded once, uploaded to Cloudflare R2, then the local file is discarded to save disk space.

5. **Excel Format**: Uses `xlsxwriter` engine for better compatibility and performance.

6. **Error Recovery**: If a subcategory fails, the scraper continues with others rather than stopping entirely.

7. **R2 Costs**: Consider R2 storage costs when running daily. Adjust lifecycle policies to archive or delete old data.

---

## 🤝 Contributing

To contribute improvements:

1. Test changes thoroughly with `debug_scraper.py`
2. Ensure Cloudflare R2 credentials are not committed
3. Update this README if adding new features
4. Verify R2 partitioning remains consistent

---

## 📧 Support

For issues or questions:
- Check [Troubleshooting](#troubleshooting) section
- Run `debug_scraper.py` for diagnostics
- Verify Cloudflare R2 credentials and permissions first

---

## 📄 License

Internal use only. Do not distribute without permission.

---

**Last Updated**: February 22, 2026  
**Version**: 2.0  
**Status**: Production Ready ✅
