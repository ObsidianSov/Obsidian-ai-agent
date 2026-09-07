"""
Osogbo RainCast AI - Inference Script

This script handles the inference pipeline for generating rainfall
forecasts using a trained RainCastConvLSTM model.

Functions:
- Fetch latest ERA5 and rainfall data
- Load trained model checkpoint
- Generate 0-6 hour rainfall forecasts
- Save forecasts as NetCDF and JSON

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

import numpy as np
import xarray as xr
import torch

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from model import RainCastConvLSTM


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run RainCastConvLSTM inference')
    parser.add_argument('--config', type=str, default='inference/config_inference.yaml',
                        help='Path to inference configuration')
    parser.add_argument('--output', type=str, default=None,
                        help='Output directory for forecasts')
    parser.add_argument('--device', type=str, default=None,
                        help='Device to use (cuda/cpu)')
    parser.add_argument('--model', type=str, default=None,
                        help='Path to model checkpoint')
    return parser.parse_args()


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def load_model(checkpoint_path: str, config: Dict, device: torch.device) -> RainCastConvLSTM:
    """
    Load trained model from checkpoint.
    
    Args:
        checkpoint_path: Path to model checkpoint
        config: Model configuration
        device: Device to load model on
    
    Returns:
        Loaded model in evaluation mode
    """
    model = RainCastConvLSTM(
        C_in=config['model']['C_in'],
        C_hidden=config['model']['C_hidden'],
        T_in=config['model']['T_in'],
        T_out=config['model']['T_out'],
        H=config['model']['H'],
        W=config['model']['W']
    )
    
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model = model.to(device)
    model.eval()
    
    return model


def fetch_latest_data(
    data_dir: str,
    lookback_hours: int = 12
) -> Tuple[np.ndarray, Dict]:
    """
    Fetch the latest available data for inference.
    
    In a production system, this would:
    1. Connect to a data API (e.g., ECMWF, GPM)
    2. Download recent ERA5 and rainfall data
    3. Regrid to the standard 81x81 grid
    
    For this demo, we simulate with synthetic data.
    
    Args:
        data_dir: Directory containing data
        lookback_hours: Number of hours to fetch
    
    Returns:
        Tuple of (input_data, metadata)
    """
    # This is a placeholder - in production, replace with actual data fetching
    # Example using CDS API:
    #
    # import cdsapi
    # c = cdsapi.Client()
    # c.retrieve(
    #     'reanalysis-era5-single-levels',
    #     {
    #         'product_type': 'reanalysis',
    #         'variable': ['total_precipitation', '2m_temperature', ...],
    #         'year': '2024',
    #         'month': '01',
    #         'day': '15',
    #         'time': ['00:00', '01:00', ...],
    #         'area': [8, 2, 4, 6],  # N, W, S, E
    #         'format': 'netcdf'
    #     },
    #     'download.nc'
    # )
    
    # Simulated data for demonstration
    T_in = lookback_hours
    C_in = 8
    H, W = 81, 81
    
    # Generate synthetic meteorological data
    np.random.seed(int(datetime.now().timestamp()) % 1000)
    data = np.random.randn(T_in, C_in, H, W).astype(np.float32)
    
    # Create metadata
    metadata = {
        'time': datetime.utcnow().isoformat(),
        'lookback_hours': lookback_hours,
        'source': 'simulated',
        'note': 'Replace with actual data fetching in production'
    }
    
    return data, metadata


def prepare_input_tensor(
    data: np.ndarray,
    config: Dict
) -> torch.Tensor:
    """
    Prepare input tensor for model inference.
    
    Args:
        data: Raw input data (T_in, C_in, H, W)
        config: Configuration dictionary
    
    Returns:
        Preprocessed input tensor (1, T_in, C_in, H, W)
    """
    # Normalize (should use same stats as training)
    # For now, use simple standardization
    mean = data.mean(axis=(0, 2, 3), keepdims=True)
    std = data.std(axis=(0, 2, 3), keepdims=True) + 1e-8
    data = (data - mean) / std
    
    # Add batch dimension
    X = torch.from_numpy(data).unsqueeze(0)
    
    return X


def run_inference(
    model: RainCastConvLSTM,
    X: torch.Tensor,
    device: torch.device
) -> np.ndarray:
    """
    Run model inference.
    
    Args:
        model: Trained RainCastConvLSTM model
        X: Input tensor (1, T_in, C_in, H, W)
        device: Device to run on
    
    Returns:
        Predicted rainfall (T_out, 1, H, W)
    """
    X = X.to(device)
    
    with torch.no_grad():
        pred = model(X)
    
    # Move to CPU and convert to numpy
    pred = pred.squeeze(0).cpu().numpy()  # (T_out, 1, H, W)
    
    # Ensure non-negative (rainfall can't be negative)
    pred = np.clip(pred, 0.0, None)
    
    return pred


def save_forecast_netcdf(
    forecast: np.ndarray,
    config: Dict,
    output_dir: Path,
    run_time: datetime
) -> Path:
    """
    Save forecast as NetCDF file.
    
    Args:
        forecast: Predicted rainfall array
        config: Configuration dictionary
        output_dir: Output directory
        run_time: Forecast run time
    
    Returns:
        Path to saved file
    """
    lat_min = config['output']['lat_min']
    lat_max = config['output']['lat_max']
    lon_min = config['output']['lon_min']
    lon_max = config['output']['lon_max']
    
    T_out = forecast.shape[0]
    
    # Create coordinate arrays
    lat = np.linspace(lat_min, lat_max, forecast.shape[2])
    lon = np.linspace(lon_min, lon_max, forecast.shape[3])
    
    # Create time array for forecast hours
    forecast_hours = np.arange(1, T_out + 1)
    
    # Create DataArray
    ds = xr.Dataset(
        {
            'rainfall': (['time', 'lat', 'lon'], forecast[:, 0])
        },
        coords={
            'time': forecast_hours,
            'lat': lat,
            'lon': lon
        },
        attrs={
            'title': 'Osogbo RainCast AI Forecast',
            'model': 'RainCastConvLSTM',
            'version': config['output']['model_version'],
            'run_time': run_time.isoformat(),
            'source': 'AI-based rainfall nowcasting',
            'units': 'mm/h'
        }
    )
    
    # Save to file
    filename = f"forecast_{run_time.strftime('%Y%m%d_%H%M%S')}.nc"
    filepath = output_dir / filename
    ds.to_netcdf(filepath)
    
    return filepath


def save_forecast_json(
    forecast: np.ndarray,
    config: Dict,
    output_dir: Path,
    run_time: datetime
) -> Path:
    """
    Save forecast as JSON file for API consumption.
    
    Args:
        forecast: Predicted rainfall array
        config: Configuration dictionary
        output_dir: Output directory
        run_time: Forecast run time
    
    Returns:
        Path to saved file
    """
    lat_min = config['output']['lat_min']
    lat_max = config['output']['lat_max']
    lon_min = config['output']['lon_min']
    lon_max = config['output']['lon_max']
    
    # Create coordinate arrays
    lat = np.linspace(lat_min, lat_max, forecast.shape[2]).tolist()
    lon = np.linspace(lon_min, lon_max, forecast.shape[3]).tolist()
    
    # Create JSON structure
    data = {
        'metadata': {
            'run_time': run_time.isoformat() + 'Z',
            'model_version': config['output']['model_version'],
            'forecast_hours': list(range(1, forecast.shape[0] + 1)),
            'grid_shape': [forecast.shape[2], forecast.shape[3]],
            'bounds': {
                'lat_min': lat_min,
                'lat_max': lat_max,
                'lon_min': lon_min,
                'lon_max': lon_max
            },
            'units': 'mm/h'
        },
        'forecasts': {}
    }
    
    # Add forecast for each hour
    for i in range(forecast.shape[0]):
        data['forecasts'][f'h{i+1}'] = {
            'hour': i + 1,
            'grid': forecast[i, 0].tolist(),
            'lat': lat,
            'lon': lon
        }
    
    # Save to file
    filename = f"forecast_{run_time.strftime('%Y%m%d_%H%M%S')}.json"
    filepath = output_dir / filename
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    return filepath


def update_latest_forecast(
    forecast: np.ndarray,
    config: Dict,
    output_dir: Path,
    run_time: datetime
):
    """
    Update the 'latest' forecast files for API serving.
    
    Args:
        forecast: Predicted rainfall array
        config: Configuration dictionary
        output_dir: Output directory
        run_time: Forecast run time
    """
    latest_dir = Path(config['api']['forecast_dir'])
    latest_dir.mkdir(parents=True, exist_ok=True)
    
    # Save as JSON (preferred for API)
    lat_min = config['output']['lat_min']
    lat_max = config['output']['lat_max']
    lon_min = config['output']['lon_min']
    lon_max = config['output']['lon_max']
    
    lat = np.linspace(lat_min, lat_max, forecast.shape[2]).tolist()
    lon = np.linspace(lon_min, lon_max, forecast.shape[3]).tolist()
    
    data = {
        'metadata': {
            'run_time': run_time.isoformat() + 'Z',
            'model_version': config['output']['model_version'],
            'forecast_hours': list(range(1, forecast.shape[0] + 1)),
            'grid_shape': [forecast.shape[2], forecast.shape[3]],
            'bounds': {
                'lat_min': lat_min,
                'lat_max': lat_max,
                'lon_min': lon_min,
                'lon_max': lon_max
            },
            'units': 'mm/h'
        },
        'forecasts': {}
    }
    
    for i in range(forecast.shape[0]):
        data['forecasts'][f'h{i+1}'] = {
            'hour': i + 1,
            'grid': forecast[i, 0].tolist(),
            'lat': lat,
            'lon': lon
        }
    
    # Save latest forecast
    latest_file = latest_dir / 'latest_forecast.json'
    with open(latest_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Also save metadata
    metadata = {
        'run_time': run_time.isoformat() + 'Z',
        'model_version': config['output']['model_version'],
        'forecast_hours': list(range(1, forecast.shape[0] + 1)),
        'grid_shape': [forecast.shape[2], forecast.shape[3]],
        'bounds': {
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lon_min': lon_min,
            'lon_max': lon_max
        }
    }
    
    metadata_file = latest_dir / 'metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)


def main():
    """Main inference function."""
    args = parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override with command line args
    if args.output:
        config['data']['output_dir'] = args.output
    if args.device:
        config['inference']['device'] = args.device
    if args.model:
        config['model']['checkpoint_path'] = args.model
    
    # Setup
    device = torch.device(config['inference']['device'])
    output_dir = Path(config['data']['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Osogbo RainCast AI - Inference")
    print("=" * 60)
    print(f"Device: {device}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Load model
    print("Loading model...")
    model_path = config['model']['checkpoint_path']
    model = load_model(model_path, config, device)
    print(f"Model loaded from: {model_path}")
    print()
    
    # Fetch latest data
    print("Fetching latest data...")
    data, data_meta = fetch_latest_data(
        config['data']['era5_dir'],
        lookback_hours=config['inference']['lookback_hours']
    )
    print(f"Data fetched: {data.shape}")
    print(f"Source: {data_meta['source']}")
    print()
    
    # Prepare input
    print("Preparing input...")
    X = prepare_input_tensor(data, config)
    print(f"Input tensor shape: {X.shape}")
    print()
    
    # Run inference
    print("Running inference...")
    run_time = datetime.utcnow()
    forecast = run_inference(model, X, device)
    print(f"Forecast shape: {forecast.shape}")
    print(f"Forecast range: [{forecast.min():.4f}, {forecast.max():.4f}] mm/h")
    print()
    
    # Save forecasts
    print("Saving forecasts...")
    
    if config['output']['save_netcdf']:
        nc_path = save_forecast_netcdf(forecast, config, output_dir, run_time)
        print(f"  NetCDF: {nc_path}")
    
    if config['output']['save_json']:
        json_path = save_forecast_json(forecast, config, output_dir, run_time)
        print(f"  JSON: {json_path}")
    
    # Update latest forecast for API
    update_latest_forecast(forecast, config, output_dir, run_time)
    print(f"  Latest forecast updated")
    
    print()
    print("=" * 60)
    print("Inference complete!")
    print(f"Run time: {run_time.isoformat()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
