# Boshamlan Offices Data Collection System

## Quick Start

### 1. Run the Complete Pipeline

```bash
cd offices
python main_offices_s3.py
```

This will:
- Scrape all offices from https://www.boshamlan.com/agents
- Filter listings published yesterday
- Get view counts for each listing
- Generate Excel files (one per office)
- Upload to S3: `s3://data-collection-dl/boshamlan-data/offices/year=YYYY/month=MM/day=DD/`

### 2. Test/Debug Mode

```bash
python debug_scraper.py
```

This runs a smaller test to verify everything works without uploading to S3.

## What Gets Scraped

### Office Information (Sheet: "info")
- Name
- URL
- Description
- Telephone
- Email
- Image
- Instagram
- Website

### Listing Information (Sheet: "main")
- Name
- URL
- Description
- Image URL
- Price
- Address Region (محافظة)
- Address Locality (منطقة)
- Views (scraped from detail page)
- Date Published

## File Structure

```
offices/
├── OfficeScraper.py           # Scrapes offices and listings
├── OfficeExcelGenerator.py    # Creates Excel files
├── OfficeS3Uploader.py        # Uploads to S3
├── main_offices_s3.py         # Main pipeline script
├── debug_scraper.py           # Testing script
├── config.example.py          # Configuration template
└── README.md                  # Full documentation
```

## S3 Structure

```
s3://data-collection-dl/
└── boshamlan-data/
    └── offices/
        └── year=2026/
            └── month=01/
                └── day=06/          # Uses filter date (yesterday)
                    ├── Office1.xlsx
                    ├── Office2.xlsx
                    └── ...
```

## Requirements

All dependencies are already in `requirements.txt`:
- playwright (for web scraping)
- beautifulsoup4 (for HTML parsing)
- openpyxl (for Excel generation)
- pandas (for data handling)
- boto3 (for S3 upload)

### Install Playwright Browsers

```bash
playwright install chromium
```

## AWS Configuration

Set environment variables:

```powershell
# Windows PowerShell
$env:AWS_ACCESS_KEY_ID="your_key"
$env:AWS_SECRET_ACCESS_KEY="your_secret"
```

Or use AWS CLI configuration:

```bash
aws configure
```

## Key Features

### ✓ Date Filtering
- By default, scrapes listings from yesterday
- Only includes offices with matching listings
- Can customize the date in the script

### ✓ View Count Extraction
- Visits each listing detail page
- Extracts view count from HTML
- Adds to Excel output

### ✓ Excel Format
- Two sheets per office
- Clean headers with styling
- Proper column widths
- Wrapped text for descriptions

### ✓ S3 Upload with Partitioning
- Date-based folder structure
- year=YYYY/month=MM/day=DD format
- Easy to query with AWS Athena

### ✓ Error Handling
- Continues if individual listings fail
- Skips offices with no matching listings
- Logs errors without stopping

## Customization

### Change Filter Date

Edit `main_offices_s3.py`:

```python
from datetime import datetime

# Scrape listings from January 5, 2026
custom_date = datetime(2026, 1, 5)
results = await pipeline.run_pipeline(filter_date=custom_date)
```

### Save Locally (No S3)

```python
# Save Excel files locally without S3 upload
results = await pipeline.run_pipeline(upload_to_s3=False)
```

Files will be in `temp_offices_excel/` folder.

### Change S3 Bucket

Edit `main_offices_s3.py`:

```python
pipeline = OfficeDataPipeline(
    region_name='us-east-1'
)
# Then modify OfficeS3Uploader initialization to use different bucket
```

## How It Works

1. **Scrape Agents Page**
   - Fetches https://www.boshamlan.com/agents
   - Extracts JSON-LD data with office information
   - Example: 120 offices found

2. **For Each Office**
   - Visit office page (e.g., https://www.boshamlan.com/agents/65152565)
   - Extract JSON-LD with listings
   - Filter by publication date

3. **For Each Listing**
   - Visit detail page (e.g., https://www.boshamlan.com/sale/lands/.../246364)
   - Find `<li class="post-info-advertising-details">` with eye SVG
   - Extract view count from `<span>`

4. **Generate Excel**
   - One file per office
   - Sheet 1: Office info
   - Sheet 2: Listings with views

5. **Upload to S3**
   - Date-partitioned structure
   - Uses filter date for folder name

## Expected Output

```
OFFICE DATA PIPELINE - 2026-01-06 10:30:15
================================================================================
Filter date: 2026-01-05
Upload to S3: True

STEP 1: Scraping office data
--------------------------------------------------------------------------------
Found 120 offices

[1/120] Processing office: مسكان المتحدة العقارية
  Found 24 listings from 2026-01-05
  Getting views for listing 1/24...
  
✓ Found 15 offices with listings from 2026-01-05
✓ Total listings: 186

STEP 2: Generating Excel files
--------------------------------------------------------------------------------
✓ Generated 15 Excel files

STEP 3: Uploading to S3
--------------------------------------------------------------------------------
✓ Uploaded 15 files to S3

PIPELINE SUMMARY
================================================================================
Offices processed: 15
Total listings: 186
Excel files generated: 15
Files uploaded to S3: 15

S3 Location:
  s3://data-collection-dl/boshamlan-data/offices/year=2026/month=01/day=05/
```

## Troubleshooting

### No offices found
- Check if yesterday had any new listings
- Try running debug_scraper.py to see what's available
- Verify website is accessible

### S3 upload fails
- Check AWS credentials
- Verify bucket exists and you have permissions
- Check bucket name spelling

### Missing view counts
- Website structure may have changed
- Check if detail pages are accessible
- Review HTML structure in browser

## Notes

- Scraping respects rate limits (0.5-1 second delays)
- Arabic names preserved in filenames
- Temporary files cleaned up after upload
- Only offices with matching listings are saved
