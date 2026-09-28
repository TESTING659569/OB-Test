# Cloudflare R2 Configuration
CF_R2_ACCESS_KEY_ID=your_access_key_here
CF_R2_SECRET_ACCESS_KEY=your_secret_key_here
CF_R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
R2_BUCKET_NAME=data-collection-dl

# Scraper Configuration
# Number of days to go back for filtering (1 = yesterday)
FILTER_DAYS_BACK=1

# Set to False to save Excel files locally without uploading to R2
UPLOAD_TO_R2=True
