"""
Boshamlan Offices Data Scraper Package

This package provides tools to scrape real estate office data from boshamlan.com,
generate Excel reports, and upload them to Cloudflare R2.

Main Components:
- OfficeScraper: Scrapes office and listing data
- OfficeS3Uploader: Handles Cloudflare R2 upload with date partitioning
"""

from .OfficeScraper import OfficeScraper
from .OfficeS3Uploader import OfficeS3Uploader

__version__ = '1.0.0'
__all__ = ['OfficeScraper', 'OfficeS3Uploader']
