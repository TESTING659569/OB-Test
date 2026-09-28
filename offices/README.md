# Boshamlan Offices Data Scraper

This folder contains scripts to scrape real estate office data from boshamlan.com/agents, generate Excel reports, and upload them to AWS S3.

## Overview

The scraper collects:
- **Office Information**: Name, description, contact details, social media links
- **Office Listings**: Properties listed by each office (filtered by date)
- **View Counts**: Number of views for each property listing

## Files

- **OfficeScraper.py**: Main scraper that extracts office and listing data from JSON-LD
- **OfficeExcelGenerator.py**: Generates Excel files with two sheets (info & main)
- **OfficeS3Uploader.py**: Handles S3 upload with date partitioning
- **main_offices_s3.py**: Orchestrates the complete pipeline
- **config.example.py**: Configuration template

## Excel File Structure

Each office gets one Excel file with two sheets:

### Sheet 1: "info"
- Office Name
- Office URL
- Description
- Telephone
- Email
- Image URL
- Instagram
- Website

### Sheet 2: "main"
- Name (listing title)
- URL (listing page)
- Description
- Image URL
- Price
- Address Region (محافظة)
- Address Locality (منطقة)
- Views (view count)
- Date Published

## S3 Storage Structure

Files are uploaded to S3 with date partitioning:

```
s3://data-collection-dl/
└── boshamlan-data/
    └── offices/
        └── year=2026/
            └── month=01/
                └── day=06/
                    ├── excel files/
                    │   ├── Office_Name_1.xlsx
                    │   ├── Office_Name_2.xlsx
                    │   └── ...
                    └── images/
                        ├── office_folder_1/
                        │   ├── image1.jpg
                        │   ├── image2.jpg
                        │   └── ...
                        └── office_folder_2/
                            └── ...
```

## Setup

### 1. Install Dependencies

```bash
pip install -r ../requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Configure AWS Credentials

Set environment variables:

```bash
# Windows PowerShell
$env:AWS_ACCESS_KEY_ID="your_access_key"
$env:AWS_SECRET_ACCESS_KEY="your_secret_key"

# Or use AWS CLI configuration
aws configure
```

## Usage

### Basic Usage (Yesterday's Data)

```bash
python main_offices_s3.py
```

This will:
1. Scrape all offices from boshamlan.com/agents
2. Get listings published yesterday
3. Extract view counts for each listing
4. Generate Excel files
5. Upload to S3 with today's date partitioning

### Custom Date

To scrape listings from a specific date, modify `main_offices_s3.py`:

```python
from datetime import datetime

# Scrape listings from a specific date
custom_date = datetime(2026, 1, 5)  # January 5, 2026
results = await pipeline.run_pipeline(filter_date=custom_date)
```

### Save Locally (No S3 Upload)

```python
# Disable S3 upload to save files locally
results = await pipeline.run_pipeline(upload_to_s3=False)
```

Files will be saved in `temp_offices_excel/` folder.

## How It Works

### Step 1: Scrape Offices
- Fetches https://www.boshamlan.com/agents
- Extracts JSON-LD data containing office information
- Parses office details (name, contact, social media)

### Step 2: Scrape Office Listings
- For each office, visits their office page
- Extracts JSON-LD data with property listings
- Filters listings by publication date (yesterday by default)

### Step 3: Get View Counts
- For each listing, visits the detail page
- Scrapes the view count from the HTML
- Pattern: `<li class="post-info-advertising-details">` with eye SVG icon

### Step 4: Generate Excel
- Creates one Excel file per office
- Two sheets: "info" (office details) and "main" (listings)
- Formatted with headers and appropriate column widths

### Step 5: Upload to S3
- Uploads to date-partitioned folders
- Structure: `year=YYYY/month=MM/day=DD/`
- Uses the filter date for partitioning

## Example Output

```
================================================================================
OFFICE DATA PIPELINE - 2026-01-06 10:30:15
================================================================================
Filter date: 2026-01-05
Upload to S3: True
================================================================================

STEP 1: Scraping office data from boshamlan.com
--------------------------------------------------------------------------------
Found 120 offices

[1/120] Processing office: مسكان المتحدة العقارية
  Found 24 listings from 2026-01-05
  Getting views for listing 1/24: ارض للبيع في السلام...
  Getting views for listing 2/24: ارض للبيع في اليرموك...
  ...

✓ Found 15 offices with listings from 2026-01-05
✓ Total listings: 186

================================================================================
STEP 2: Generating Excel files
--------------------------------------------------------------------------------
Generated Excel file: temp_offices_excel/مسكان_المتحدة_العقارية.xlsx
...

✓ Generated 15 Excel files

================================================================================
STEP 3: Uploading to S3
--------------------------------------------------------------------------------
Uploading مسكان_المتحدة_العقارية.xlsx to s3://data-collection-dl/boshamlan-data/offices/year=2026/month=01/day=05/excel files/...
Successfully uploaded to s3://data-collection-dl/boshamlan-data/offices/year=2026/month=01/day=05/excel files/مسكان_المتحدة_العقارية.xlsx
...

✓ Uploaded 15 files to S3

================================================================================
PIPELINE SUMMARY
================================================================================
Offices processed: 15
Total listings: 186
Excel files generated: 15
Files uploaded to S3: 15

S3 Locations:
  Excel files: s3://data-collection-dl/boshamlan-data/offices/year=2026/month=01/day=05/excel files/
  Images: s3://data-collection-dl/boshamlan-data/offices/year=2026/month=01/day=05/images/
================================================================================

✓ Pipeline completed successfully!
```

## Filtering Logic

- **Date Filter**: Only listings with `datePublished` matching the filter date are included
- **Office Filter**: Only offices with at least one matching listing are saved
- **Default**: Filter date is yesterday (today - 1 day)

## Error Handling

- Retries on network errors
- Continues if individual listings fail
- Logs errors without stopping the pipeline
- Skips offices with no matching listings

## Notes

- Arabic office names are preserved in filenames
- View counts may be None if scraping fails
- Rate limiting between requests (0.5-1 second delays)
- Temporary files are cleaned up after S3 upload

## Troubleshooting

### No offices found
- Check if the date has listings (yesterday might have no new listings)
- Verify the website structure hasn't changed
- Check internet connection

### S3 upload fails
- Verify AWS credentials are set correctly
- Check bucket permissions
- Verify bucket name is correct

### View counts are None
- The listing detail page structure may have changed
- Check if the page loaded correctly
- Review the HTML structure of the listing page

## License

This scraper is for data collection purposes only. Respect website terms of service and robots.txt.
