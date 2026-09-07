"""
Osogbo RainCast AI - ERA5 Data Downloader

Downloads ERA5 reanalysis data for Southwest Nigeria region.

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria

Note: Requires CDS API credentials. Register at https://cds.climate.copernicus.eu/
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

try:
    import cdsapi
except ImportError:
    print("Warning: cdsapi not installed. Install with: pip install cdsapi")


# ERA5 Variables
ERA5_VARIABLES = [
    'total_precipitation',           # tp
    '2m_temperature',                 # 2t
    '2m_dewpoint_temperature',        # 2d
    '10m_u_component_of_wind',        # u10
    '10m_v_component_of_wind',       # v10
    'surface_pressure',               # sp
    'total_column_water_vapour',     # tcwv
    'convective_available_potential_energy'  # cape
]


def parse_args():
    parser = argparse.ArgumentParser(description='Download ERA5 data')
    parser.add_argument('--start', type=int, required=True, help='Start year')
    parser.add_argument('--end', type=int, required=True, help='End year')
    parser.add_argument('--output', type=str, default='data/raw/era5', help='Output directory')
    parser.add_argument('--month', type=int, nargs='+', default=list(range(1, 13)),
                        help='Months to download (1-12)')
    parser.add_argument('--dry-run', action='store_true', help='Print without downloading')
    return parser.parse_args()


def download_era5_data(args):
    """
    Download ERA5 data using CDS API.
    
    Region: Southwest Nigeria (4-8°N, 2-6°E)
    """
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize CDS API client
    c = cdsapi.Client()
    
    for year in range(args.start, args.end + 1):
        for month in args.month:
            print(f"Downloading ERA5 data for {year}-{month:02d}...")
            
            filename = f"era5_{year}_{month:02d}.nc"
            filepath = output_dir / filename
            
            if filepath.exists():
                print(f"  File exists, skipping: {filename}")
                continue
            
            if args.dry_run:
                print(f"  Would download: {filename}")
                continue
            
            try:
                c.retrieve(
                    'reanalysis-era5-single-levels',
                    {
                        'product_type': 'reanalysis',
                        'variable': ERA5_VARIABLES,
                        'year': str(year),
                        'month': f'{month:02d}',
                        'day': [
                            '01', '02', '03', '04', '05', '06',
                            '07', '08', '09', '10', '11', '12',
                            '13', '14', '15', '16', '17', '18',
                            '19', '20', '21', '22', '23', '24',
                            '25', '26', '27', '28', '29', '30', '31'
                        ],
                        'time': [
                            '00:00', '01:00', '02:00', '03:00', '04:00', '05:00',
                            '06:00', '07:00', '08:00', '09:00', '10:00', '11:00',
                            '12:00', '13:00', '14:00', '15:00', '16:00', '17:00',
                            '18:00', '19:00', '20:00', '21:00', '22:00', '23:00'
                        ],
                        'area': [8, 2, 4, 6],  # N, W, S, E
                        'format': 'netcdf'
                    },
                    str(filepath)
                )
                print(f"  Downloaded: {filename}")
            except Exception as e:
                print(f"  Error downloading {filename}: {e}")


def main():
    args = parse_args()
    print("=" * 60)
    print("Osogbo RainCast AI - ERA5 Data Downloader")
    print("=" * 60)
    print(f"Period: {args.start} - {args.end}")
    print(f"Output: {args.output}")
    print()
    
    download_era5_data(args)
    
    print("\nDownload complete!")


if __name__ == "__main__":
    main()
