"""
Osogbo RainCast AI - GPM IMERG Data Downloader

Downloads GPM IMERG precipitation data for Southwest Nigeria region.

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria

Note: Data can be downloaded from NASA's GES DISC or Google Cloud Storage.
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

import requests


def parse_args():
    parser = argparse.ArgumentParser(description='Download GPM IMERG data')
    parser.add_argument('--start', type=int, required=True, help='Start year')
    parser.add_argument('--end', type=int, required=True, help='End year')
    parser.add_argument('--output', type=str, default='data/raw/gpm', help='Output directory')
    parser.add_argument('--product', type=str, default='IMERG-Final', 
                        choices=['IMERG-Final', 'IMERG-Late', 'IMERG-Early'],
                        help='GPM product type')
    parser.add_argument('--dry-run', action='store_true', help='Print without downloading')
    return parser.parse_args()


def download_gpm_data(args):
    """
    Download GPM IMERG data.
    
    In production, this would connect to:
    - NASA GES DISC: https://gpm1.gesdisc.eosdis.nasa.gov/
    - Google Cloud Storage: gs://gpm-parts/
    - Direct HDF5 downloads from NASA
    
    Region: Southwest Nigeria (4-8°N, 2-6°E)
    """
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Note: GPM data download requires NASA Earthdata credentials.")
    print("Please use one of the following methods:")
    print("1. NASA GES DISC: https://gpm1.gesdisc.eosdis.nasa.gov/")
    print("2. Google Cloud: gs://gpm-parts/")
    print("3. CHIRPS (alternative): https://chc-ewx2.ucsb.edu/")
    print()
    
    # Example download URL pattern (requires authentication)
    base_url = "https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/"
    
    for year in range(args.start, args.end + 1):
        print(f"Year {year}:")
        
        if args.product == 'IMERG-Final':
            # Monthly files
            for month in range(1, 13):
                filename = f"3B-MO.MS.MRG.3IMERG.{year}{month:02d}-S000000-S235959.V06B.HDF5"
                
                if args.dry_run:
                    print(f"  Would download: {filename}")
                else:
                    print(f"  Placeholder: {filename} (manual download required)")
        
    print("\nFor automated downloading, consider using:")
    print("- pyGPM library")
    print("- rioxarray with GCS") 
    print("- CHIRPS (simpler alternative)")


def download_chirps_data(args):
    """
    Alternative: Download CHIRPS data (simpler format).
    """
    output_dir = Path(args.output)
    chirps_dir = output_dir / 'chirps'
    chirps_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"CHIRPS data directory: {chirps_dir}")
    print("Download from: https://chc-ewx2.ucsb.edu/")
    print("Format: NetCDF or GeoTIFF")


def main():
    args = parse_args()
    print("=" * 60)
    print("Osogbo RainCast AI - GPM IMERG Data Downloader")
    print("=" * 60)
    print(f"Period: {args.start} - {args.end}")
    print(f"Product: {args.product}")
    print(f"Output: {args.output}")
    print()
    
    download_gpm_data(args)
    
    print("\nNote: This is a placeholder. Implement actual download logic")
    print("or use pre-downloaded data.")


if __name__ == "__main__":
    main()
