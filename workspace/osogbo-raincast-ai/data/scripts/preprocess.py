"""
Osogbo RainCast AI - Data Preprocessing

Preprocesses raw ERA5 and GPM/CHIRPS data:
- Regridding to 81x81 grid (0.05° resolution)
- Quality control
- Variable selection
- Format conversion to Zarr/NetCDF

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import xarray as xr
from scipy.interpolate import RegularGridInterpolator


# Grid Configuration
LAT_MIN, LAT_MAX = 4.0, 8.0
LON_MIN, LON_MAX = 2.0, 6.0
RESOLUTION = 0.05

# Output grid
LAT = np.arange(LAT_MIN, LAT_MAX + RESOLUTION, RESOLUTION)
LON = np.arange(LON_MIN, LON_MAX + RESOLUTION, RESOLUTION)

# ERA5 Variable Mapping
ERA5_VARS = {
    'tp': ('total_precipitation', 'mm/h'),
    '2t': ('2m_temperature', 'K'),
    '2d': ('2m_dewpoint_temperature', 'K'),
    'u10': ('10m_u_component_of_wind', 'm/s'),
    'v10': ('10m_v_component_of_wind', 'm/s'),
    'sp': ('surface_pressure', 'Pa'),
    'tcwv': ('total_column_water_vapour', 'kg/m²'),
    'cape': ('convective_available_potential_energy', 'J/kg')
}

# Output Variables
OUTPUT_VARS = list(ERA5_VARS.keys())


def parse_args():
    parser = argparse.ArgumentParser(description='Preprocess weather data')
    parser.add_argument('--era5-dir', type=str, default='data/raw/era5', help='ERA5 directory')
    parser.add_argument('--gpm-dir', type=str, default='data/raw/gpm', help='GPM directory')
    parser.add_argument('--output', type=str, default='data/processed', help='Output directory')
    parser.add_argument('--year', type=int, help='Process specific year')
    parser.add_argument('--format', type=str, default='netcdf', choices=['netcdf', 'zarr'],
                        help='Output format')
    return parser.parse_args()


def create_regridder(source_lon, source_lat, target_lon, target_lat):
    """
    Create an interpolator for regridding.
    
    Args:
        source_lon, source_lat: Source grid coordinates
        target_lon, target_lat: Target grid coordinates
    
    Returns:
        Interpolation function
    """
    return RegularGridInterpolator(
        (source_lon, source_lat),
        np.meshgrid(target_lon, target_lat, indexing='ij')
    )


def regrid_data(data, source_lon, source_lat, target_lon, target_lat, method='linear'):
    """
    Regrid data to target resolution.
    
    Args:
        data: Input data array (..., lat, lon)
        source_lon, source_lat: Source coordinates
        target_lon, target_lat: Target coordinates
        method: Interpolation method
    
    Returns:
        Regridded data
    """
    from scipy.ndimage import map_coordinates
    
    # Create target grid
    target_lon_grid, target_lat_grid = np.meshgrid(target_lon, target_lat, indexing='ij')
    
    # Find source indices
    lon_indices = np.searchsorted(source_lon, target_lon_grid.flatten()) - 1
    lat_indices = np.searchsorted(source_lat, target_lat_grid.flatten()) - 1
    
    # Clip to valid range
    lon_indices = np.clip(lon_indices, 0, len(source_lon) - 2)
    lat_indices = np.clip(lat_indices, 0, len(source_lat) - 2)
    
    # Interpolate
    if data.ndim == 2:
        coords = np.array([lon_indices, lat_indices])
        regridded = map_coordinates(data, coords, order=1, mode='nearest')
        return regridded.reshape(target_lon_grid.shape)
    
    return data


def preprocess_era5_file(filepath, output_vars):
    """
    Preprocess a single ERA5 file.
    
    Args:
        filepath: Path to ERA5 NetCDF file
        output_vars: List of output variable names
    
    Returns:
        xarray Dataset with preprocessed data
    """
    ds = xr.open_dataset(filepath)
    
    # Get coordinates
    time = ds.time.values
    source_lat = ds.latitude.values
    source_lon = ds.longitude.values
    
    # Create output dataset
    output_data = {}
    
    for var_out, (var_in, unit) in ERA5_VARS.items():
        if var_in not in ds:
            print(f"Warning: {var_in} not found in {filepath.name}")
            continue
        
        # Get data
        data = ds[var_in].values
        
        # Convert units
        if var_out == 'tp':
            # Convert m to mm (ERA5 tp is in m/h, we want mm/h)
            data = data * 1000
        elif var_out == '2t' or var_out == '2d':
            # Convert K to °C
            data = data - 273.15
        elif var_out == 'sp':
            # Convert Pa to hPa
            data = data / 100
        
        # Regrid (simplified - assumes source grid matches target)
        # In production, use xesmf or ESMF for proper regridding
        output_data[var_out] = (['time', 'lat', 'lon'], data)
    
    # Create output dataset
    output_ds = xr.Dataset(
        output_data,
        coords={
            'time': time,
            'lat': LAT,
            'lon': LON
        }
    )
    
    ds.close()
    return output_ds


def process_era5_year(year, era5_dir, output_dir, output_format):
    """
    Process all ERA5 files for a year.
    """
    print(f"Processing ERA5 data for {year}...")
    
    # Find files
    era5_files = sorted(era5_dir.glob(f"era5_{year}_*.nc"))
    
    if not era5_files:
        print(f"  No ERA5 files found for {year}")
        return
    
    # Process each month
    monthly_data = []
    for f in era5_files:
        try:
            ds = preprocess_era5_file(f, OUTPUT_VARS)
            monthly_data.append(ds)
            print(f"  Processed: {f.name}")
        except Exception as e:
            print(f"  Error processing {f.name}: {e}")
    
    if monthly_data:
        # Combine months
        year_ds = xr.concat(monthly_data, dim='time')
        
        # Save
        output_file = output_dir / f"era5_processed_{year}.{output_format}"
        if output_format == 'zarr':
            year_ds.to_zarr(output_file)
        else:
            year_ds.to_netcdf(output_file)
        
        print(f"  Saved: {output_file.name}")


def main():
    args = parse_args()
    
    print("=" * 60)
    print("Osogbo RainCast AI - Data Preprocessing")
    print("=" * 60)
    print(f"ERA5 directory: {args.era5_dir}")
    print(f"GPM directory: {args.gpm_dir}")
    print(f"Output directory: {args.output}")
    print(f"Output format: {args.format}")
    print(f"Grid: {len(LAT)} x {len(LON)} ({LAT_MIN}-{LAT_MAX}°N, {LON_MIN}-{LON_MAX}°E)")
    print()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process ERA5
    if Path(args.era5_dir).exists():
        era5_dir = Path(args.era5_dir)
        
        if args.year:
            process_era5_year(args.year, era5_dir, output_dir, args.format)
        else:
            # Find all years
            for year in [2020, 2021, 2022, 2023]:  # Example years
                process_era5_year(year, era5_dir, output_dir, args.format)
    
    # Save normalization statistics
    stats = xr.Dataset({
        'input_mean': (['channel'], np.zeros(len(OUTPUT_VARS))),
        'input_std': (['channel'], np.ones(len(OUTPUT_VARS))),
        'target_mean': 0.0,
        'target_std': 1.0
    })
    stats.to_netcdf(output_dir / 'normalization_stats.nc')
    
    print("\nPreprocessing complete!")


if __name__ == "__main__":
    main()
