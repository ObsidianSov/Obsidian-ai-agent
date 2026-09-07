"""
Osogbo RainCast AI - PyTorch Dataset

This module implements the RainCastDataset class for loading
preprocessed ERA5 and rainfall data for training and evaluation.

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
"""

import os
import torch
import numpy as np
import xarray as xr
from torch.utils.data import Dataset
from typing import Tuple, Optional, List, Dict
from pathlib import Path


class RainCastDataset(Dataset):
    """
    PyTorch Dataset for Rainfall Nowcasting
    
    Loads preprocessed data and returns input/target pairs for
    training the RainCastConvLSTM model.
    
    Args:
        data_dir: Directory containing processed NetCDF/Zarr files
        years: List of years to load
        split: 'train', 'val', or 'test'
        T_in: Input sequence length (default: 12)
        T_out: Forecast horizon (default: 6)
        transform: Optional transform to apply
    
    Input Shape:
        X: (T_in, C_in, H, W) - Meteorological fields
        
    Target Shape:
        Y: (T_out, 1, H, W) - Rainfall fields
    
    Example:
        >>> dataset = RainCastDataset(
        ...     data_dir="data/processed",
        ...     years=[2005, 2018],
        ...     split="train"
        ... )
        >>> X, Y = dataset[0]  # X: (12, 8, 81, 81), Y: (6, 1, 81, 81)
    """
    
    # Variable names in the processed data
    INPUT_VARS = [
        'tp',    # Total precipitation
        't2m',   # 2m temperature
        'd2m',   # 2m dewpoint
        'u10',   # 10m u-wind
        'v10',   # 10m v-wind
        'sp',    # Surface pressure
        'tcwv',  # Total column water vapor
        'cape'   # Convective available potential energy
    ]
    
    TARGET_VAR = 'precipitation'  # GPM IMERG / CHIRPS rainfall
    
    def __init__(
        self,
        data_dir: str,
        years: List[int],
        split: str = 'train',
        T_in: int = 12,
        T_out: int = 6,
        transform: Optional[callable] = None
    ):
        self.data_dir = Path(data_dir)
        self.years = years
        self.split = split
        self.T_in = T_in
        self.T_out = T_out
        self.transform = transform
        
        # Find data files
        self.data_files = self._find_data_files()
        
        # Load and index all valid samples
        self.samples = self._build_sample_index()
        
        # Compute normalization statistics (can be loaded from file)
        self._load_normalization_stats()
    
    def _find_data_files(self) -> List[Path]:
        """Find all processed data files for the specified years."""
        files = []
        for year in self.years:
            pattern = f"*{year}*.nc"  # or *.zarr
            year_files = list(self.data_dir.glob(pattern))
            files.extend(year_files)
        return sorted(files)
    
    def _build_sample_index(self) -> List[Dict]:
        """
        Build index of all valid samples.
        
        Each sample is defined by (file_idx, time_idx) pointing to
        the start of an input sequence.
        """
        samples = []
        
        for file_idx, data_file in enumerate(self.data_files):
            try:
                # Open dataset
                with xr.open_dataset(data_file) as ds:
                    # Get number of time steps
                    n_times = len(ds.time)
                    
                    # Calculate number of valid samples
                    # Need T_in + T_out consecutive hours
                    n_samples = n_times - self.T_in - self.T_out + 1
                    
                    for t in range(n_samples):
                        samples.append({
                            'file_idx': file_idx,
                            'time_idx': t,
                            'file_path': str(data_file)
                        })
            except Exception as e:
                print(f"Warning: Could not load {data_file}: {e}")
                continue
        
        print(f"Loaded {len(samples)} samples from {len(self.data_files)} files "
              f"for {self.split} split (years: {self.years})")
        
        return samples
    
    def _load_normalization_stats(self):
        """Load or compute normalization statistics."""
        stats_file = self.data_dir / 'normalization_stats.nc'
        
        if stats_file.exists():
            # Load precomputed statistics
            ds = xr.open_dataset(stats_file)
            self.input_mean = ds['input_mean'].values
            self.input_std = ds['input_std'].values
            self.target_mean = ds['target_mean'].values.item()
            self.target_std = ds['target_std'].values.item()
        else:
            # Default normalization (can be computed from data)
            # Input: 8 channels
            self.input_mean = np.zeros(len(self.INPUT_VARS))
            self.input_std = np.ones(len(self.INPUT_VARS))
            self.target_mean = 0.0
            self.target_std = 1.0
    
    def __len__(self) -> int:
        """Return number of samples in dataset."""
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Get a single sample.
        
        Args:
            idx: Sample index
        
        Returns:
            Tuple of (input, target) tensors
        """
        sample_info = self.samples[idx]
        
        # Open the data file
        with xr.open_dataset(sample_info['file_path']) as ds:
            # Get input sequence: [time_idx : time_idx + T_in]
            input_start = sample_info['time_idx']
            input_end = input_start + self.T_in
            
            # Get target: [time_idx + T_in : time_idx + T_in + T_out]
            target_start = input_end
            target_end = target_start + self.T_out
            
            # Extract input variables
            input_data = []
            for var in self.INPUT_VARS:
                if var in ds:
                    var_data = ds[var].values[input_start:input_end]
                    # Normalize
                    var_data = (var_data - self.input_mean[len(input_data)]) / (
                        self.input_std[len(input_data)] + 1e-8
                    )
                    input_data.append(var_data)
            
            # Stack to (T_in, C_in, H, W)
            X = np.stack(input_data, axis=1).astype(np.float32)
            
            # Extract target (rainfall)
            Y = ds[self.TARGET_VAR].values[target_start:target_end]
            Y = np.expand_dims(Y, axis=1).astype(np.float32)  # (T_out, 1, H, W)
            
            # Handle missing values
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
            Y = np.nan_to_num(Y, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Convert to tensors
        X = torch.from_numpy(X)
        Y = torch.from_numpy(Y)
        
        # Ensure non-negative rainfall
        Y = torch.clamp(Y, min=0.0)
        
        # Apply transform if provided
        if self.transform is not None:
            X, Y = self.transform(X, Y)
        
        return X, Y
    
    def get_time_info(self, idx: int) -> Dict:
        """Get time information for a sample."""
        sample_info = self.samples[idx]
        
        with xr.open_dataset(sample_info['file_path']) as ds:
            time_idx = sample_info['time_idx']
            time = ds.time.values[time_idx]
        
        return {
            'time': time,
            'file': sample_info['file_path']
        }


class RandomCrop:
    """Random spatial crop for data augmentation."""
    
    def __init__(self, crop_size: int = 64):
        self.crop_size = crop_size
    
    def __call__(self, X: torch.Tensor, Y: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        B, C, H, W = X.shape
        _, _, H_out, W_out = Y.shape
        
        if self.crop_size >= H:
            return X, Y
        
        # Random crop position
        top = np.random.randint(0, H - self.crop_size + 1)
        left = np.random.randint(0, W - self.crop_size + 1)
        
        # Crop input
        X = X[:, :, top:top+self.crop_size, left:left+self.crop_size]
        
        # Crop target (same region)
        Y = Y[:, :, top:top+self.crop_size, left:left+self.crop_size]
        
        return X, Y


class RandomFlip:
    """Random horizontal/vertical flip for data augmentation."""
    
    def __init__(self, h_flip: float = 0.5, v_flip: float = 0.5):
        self.h_flip_prob = h_flip
        self.v_flip_prob = v_flip
    
    def __call__(self, X: torch.Tensor, Y: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        if np.random.random() < self.h_flip_prob:
            X = torch.flip(X, dims=[-1])
            Y = torch.flip(Y, dims=[-1])
        
        if np.random.random() < self.v_flip_prob:
            X = torch.flip(X, dims=[-2])
            Y = torch.flip(Y, dims=[-2])
        
        return X, Y


def create_dataloaders(config: dict) -> Tuple:
    """
    Create train, validation, and test dataloaders from config.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Tuple of (train_loader, val_loader, test_loader)
    """
    from torch.utils.data import DataLoader
    
    data_dir = config['data']['root_dir']
    train_years = config['data']['train_years']
    val_years = config['data']['val_years']
    test_years = config['data']['test_years']
    
    T_in = config['model']['T_in']
    T_out = config['model']['T_out']
    batch_size = config['training']['batch_size']
    
    # Create datasets
    train_dataset = RainCastDataset(
        data_dir=data_dir,
        years=train_years,
        split='train',
        T_in=T_in,
        T_out=T_out
    )
    
    val_dataset = RainCastDataset(
        data_dir=data_dir,
        years=val_years,
        split='val',
        T_in=T_in,
        T_out=T_out
    )
    
    test_dataset = RainCastDataset(
        data_dir=data_dir,
        years=test_years,
        split='test',
        T_in=T_in,
        T_out=T_out
    )
    
    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=2,
        pin_memory=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=config['validation']['batch_size'],
        shuffle=False,
        num_workers=2,
        pin_memory=True
    )
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=config['testing']['batch_size'],
        shuffle=False,
        num_workers=2,
        pin_memory=True
    )
    
    return train_loader, val_loader, test_loader


if __name__ == "__main__":
    # Test dataset
    print("Testing RainCastDataset...")
    
    # Create dummy test
    class DummyDataset(Dataset):
        def __len__(self):
            return 100
        
        def __getitem__(self, idx):
            X = torch.randn(12, 8, 81, 81)
            Y = torch.randn(6, 1, 81, 81).abs()
            return X, Y
    
    dataset = DummyDataset()
    X, Y = dataset[0]
    
    print(f"Input shape: {X.shape}")
    print(f"Target shape: {Y.shape}")
    
    print("\n✅ Dataset test passed!")
