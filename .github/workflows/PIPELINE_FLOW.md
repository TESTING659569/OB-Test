# GitHub Actions Pipeline Flow

## Overview
The pipeline orchestrates two scraping workflows and tracks their execution status.

## Pipeline Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    PIPELINE TRIGGER                         │
│  • Schedule: Daily at 12:00 AM UTC                         │
│  • Manual: GitHub Actions UI                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 1: Unified Scraper Workflow               │
│  Workflow: scraper.yml                                      │
│                                                             │
│  ┌───────────────────────────────────────────────┐         │
│  │ JOB 1: Properties Scraper                     │         │
│  │ ┌───────────────────────────────────────────┐│         │
│  │ │ 1. Checkout code                          ││         │
│  │ │ 2. Setup Python 3.11                      ││         │
│  │ │ 3. Install dependencies                   ││         │
│  │ │ 4. Install Playwright (Chromium)          ││         │
│  │ │ 5. Run properties scraper:                ││         │
│  │ │    - Scrape rent/sale/exchange categories ││         │
│  │ │    - Upload images to S3                  ││         │
│  │ │    - Generate Excel files                 ││         │
│  │ │    - Upload Excel to S3                   ││         │
│  │ └───────────────────────────────────────────┘│         │
│  │ Output: status = success/failure              │         │
│  └───────────────────────────────────────────────┘         │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────┐         │
│  │ JOB 2: Offices Scraper (needs: properties)   │         │
│  │ ┌───────────────────────────────────────────┐│         │
│  │ │ 1. Checkout code                          ││         │
│  │ │ 2. Setup Python 3.11                      ││         │
│  │ │ 3. Install dependencies                   ││         │
│  │ │ 4. Install Playwright (Chromium)          ││         │
│  │ │ 5. Run offices scraper:                   ││         │
│  │ │    - Scrape office information            ││         │
│  │ │    - Scrape office listings               ││         │
│  │ │    - Get view counts                      ││         │
│  │ │    - Upload images to S3                  ││         │
│  │ │    - Generate Excel files                 ││         │
│  │ │    - Upload Excel to S3                   ││         │
│  │ └───────────────────────────────────────────┘│         │
│  │ Output: status = success/failure              │         │
│  └───────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              JOB 3: Update Status                           │
│  Depends on: Jobs 1 & 2 (always runs)                      │
│  ┌───────────────────────────────────────────────┐         │
│  │ 1. Checkout code                              │         │
│  │ 2. Determine overall status:                  │         │
│  │    - Collect properties status                │         │
│  │    - Collect offices status                   │         │
│  │    - Calculate overall status                 │         │
│  │ 3. Create status.json:                        │         │
│  │    - Current date/timestamp                   │         │
│  │    - Overall status                           │         │
│  │    - Individual scraper statuses              │         │
│  │    - Pipeline run metadata                    │         │
│  │ 4. Commit and push status.json                │         │
│  │ 5. Upload status as artifact                  │         │
│  └───────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  status.json    │
                   │  in repository  │
                   └─────────────────┘
```

## Status Determination Logic

```
Properties Status     Offices Status      Overall Status
─────────────────     ──────────────      ──────────────
   success        +      success      →      success
   success        +      failure      →      failed
   failure        +      success      →      failed
   failure        +      failure      →      failed
   success        +      skipped      →      failed
   failure        +      skipped      →      failed
```

## Files Generated

### Repository Files
- `status.json` - Committed to repository root
  - Updated after each pipeline run
  - Contains execution status and metadata
  - Accessible via git history

### Artifacts (ephemeral, 30 days retention)
- `pipeline-status` artifact
  - Contains status.json snapshot
  - Downloadable from GitHub Actions UI
  - Retained for 30 days

### S3 Files
Both scrapers upload to S3 with date partitioning:

**Properties:**
```
s3://data-collection-dl/boshamlan-data/properties/
  └── year=2026/month=03/day=15/
      ├── excel files/
      │   ├── rent.xlsx
      │   ├── sale.xlsx
      │   └── exchange.xlsx
      └── images/
          ├── rent/
          ├── sale/
          └── exchange/
```

**Offices:**
```
s3://data-collection-dl/boshamlan-data/offices/
  └── year=2026/month=03/day=15/
      ├── excel files/
      │   └── offices_YYYYMMDD_HHMMSS.xlsx
      └── images/
          └── [office_name]/
```


## Monitoring

### Real-time Monitoring
1. Go to **Actions** tab in GitHub
2. View running workflow
3. Click on jobs to see real-time logs

### Historical Monitoring
1. Check `status.json` in repository
2. View git history of status.json
3. Download artifacts from past runs (30 days)

### Alerts
Set up GitHub Actions notifications:
- Repository Settings → Notifications
- Configure email/Slack for workflow failures
