"""
Osogbo RainCast AI - Loss Functions

This module implements loss functions for rainfall nowcasting,
including weighted MSE emphasizing heavy rainfall events.

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple


class WeightedMSELoss(nn.Module):
    """
    Weighted Mean Squared Error Loss
    
    Weights are applied based on rainfall intensity to emphasize
    heavy rainfall events which are more impactful.
    
    Weight mapping:
        - Light rain (< 1 mm/h): w = 1
        - Moderate rain (1-5 mm/h): w = 2
        - Heavy rain (>= 5 mm/h): w = 4
    
    Args:
        threshold_light (float): Upper threshold for light rain (default: 1.0)
        threshold_heavy (float): Lower threshold for heavy rain (default: 5.0)
        reduction (str): 'mean', 'sum', or 'none'
    """
    
    def __init__(
        self,
        threshold_light: float = 1.0,
        threshold_heavy: float = 5.0,
        reduction: str = 'mean'
    ):
        super(WeightedMSELoss, self).__init__()
        
        self.threshold_light = threshold_light
        self.threshold_heavy = threshold_heavy
        self.reduction = reduction
    
    def forward(
        self, 
        pred: torch.Tensor, 
        target: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute weighted MSE loss.
        
        Args:
            pred: Predicted rainfall (B, T, 1, H, W)
            target: Target rainfall (B, T, 1, H, W)
        
        Returns:
            Weighted MSE loss
        """
        # Ensure non-negative predictions (rainfall can't be negative)
        pred = torch.clamp(pred, min=0.0)
        
        # Compute squared error
        squared_error = (pred - target) ** 2
        
        # Create weight map based on target values
        weights = torch.ones_like(target)
        
        # Light rain: w = 1 (default)
        # Moderate rain: w = 2
        # Heavy rain: w = 4
        weights = torch.where(
            target < self.threshold_light,
            torch.tensor(1.0, device=target.device),
            weights
        )
        weights = torch.where(
            (target >= self.threshold_light) & (target < self.threshold_heavy),
            torch.tensor(2.0, device=target.device),
            weights
        )
        weights = torch.where(
            target >= self.threshold_heavy,
            torch.tensor(4.0, device=target.device),
            weights
        )
        
        # Apply weights
        weighted_se = weights * squared_error
        
        # Apply reduction
        if self.reduction == 'mean':
            return weighted_se.mean()
        elif self.reduction == 'sum':
            return weighted_se.sum()
        else:
            return weighted_se


class CombinedLoss(nn.Module):
    """
    Combined MSE + MAE Loss
    
    Combines weighted MSE with MAE for more robust training.
    The MAE term helps with outliers while MSE focuses on
    overall accuracy.
    
    Args:
        mse_weight (float): Weight for MSE component (default: 1.0)
        mae_weight (float): Weight for MAE component (default: 0.1)
        threshold_light (float): Threshold for light rain
        threshold_heavy (float): Threshold for heavy rain
    """
    
    def __init__(
        self,
        mse_weight: float = 1.0,
        mae_weight: float = 0.1,
        threshold_light: float = 1.0,
        threshold_heavy: float = 5.0
    ):
        super(CombinedLoss, self).__init__()
        
        self.mse_weight = mse_weight
        self.mae_weight = mae_weight
        
        self.mse_loss = WeightedMSELoss(
            threshold_light=threshold_light,
            threshold_heavy=threshold_heavy
        )
    
    def forward(
        self,
        pred: torch.Tensor,
        target: torch.Tensor
    ) -> Tuple[torch.Tensor, dict]:
        """
        Compute combined loss.
        
        Returns:
            Tuple of (total_loss, loss_components)
        """
        # Ensure non-negative predictions
        pred = torch.clamp(pred, min=0.0)
        
        # Compute MSE component
        mse = self.mse_loss(pred, target)
        
        # Compute MAE component with same weighting
        weights = torch.ones_like(target)
        weights = torch.where(
            target < 1.0,
            torch.tensor(1.0, device=target.device),
            torch.where(
                target < 5.0,
                torch.tensor(2.0, device=target.device),
                torch.tensor(4.0, device=target.device)
            )
        )
        mae = (weights * torch.abs(pred - target)).mean()
        
        # Combine
        total_loss = self.mse_weight * mse + self.mae_weight * mae
        
        # Return components for logging
        components = {
            'mse': mse.item(),
            'mae': mae.item(),
            'total': total_loss.item()
        }
        
        return total_loss, components


class LogcoshLoss(nn.Module):
    """
    Log-Cosh Loss Function
    
    Behaves like MSE for small errors but has less penalty for
    large errors compared to MSE.
    
    Reference: "A Unified Approach to Interpreting Model Predictions" (Lundberg & Lee, 2017)
    """
    
    def __init__(self):
        super(LogcoshLoss, self).__init__()
    
    def forward(
        self, 
        pred: torch.Tensor, 
        target: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute log-cosh loss.
        
        Args:
            pred: Predicted values
            target: Target values
        
        Returns:
            Log-cosh loss
        """
        pred = torch.clamp(pred, min=0.0)
        diff = pred - target
        return torch.mean(torch.log(torch.cosh(diff + 1e-12)))


class HeavyRainfallLoss(nn.Module):
    """
    Specialized Loss for Heavy Rainfall Detection
    
    Combines:
    1. Weighted MSE for overall accuracy
    2. Focal loss component for hard-to-predict events
    3. Boundary loss for sharp rainfall gradients
    
    Args:
        mse_weight (float): Weight for MSE
        focal_weight (float): Weight for focal component
        focal_gamma (float): Focusing parameter for focal loss
    """
    
    def __init__(
        self,
        mse_weight: float = 0.7,
        focal_weight: float = 0.3,
        focal_gamma: float = 2.0
    ):
        super(HeavyRainfallLoss, self).__init__()
        
        self.mse_weight = mse_weight
        self.focal_weight = focal_weight
        self.focal_gamma = focal_gamma
        
        self.mse_loss = WeightedMSELoss()
    
    def focal_loss(
        self,
        pred: torch.Tensor,
        target: torch.Tensor
    ) -> torch.Tensor:
        """
        Focal loss for heavy rainfall events.
        
        Focal loss reduces the loss contribution from easy examples
        and focuses on hard examples.
        """
        pred = torch.clamp(pred, min=1e-6, max=1.0)
        
        # Binary target: 1 if rainfall >= 5mm/h, 0 otherwise
        binary_target = (target >= 5.0).float()
        
        # Focal weights
        pt = pred * binary_target + (1 - pred) * (1 - binary_target)
        focal_weight = (1 - pt) ** self.focal_gamma
        
        # Cross entropy
        ce = -binary_target * torch.log(pred) - (1 - binary_target) * torch.log(1 - pred)
        
        return (focal_weight * ce).mean()
    
    def forward(
        self,
        pred: torch.Tensor,
        target: torch.Tensor
    ) -> Tuple[torch.Tensor, dict]:
        """
        Compute combined heavy rainfall loss.
        """
        mse = self.mse_loss(pred, target)
        focal = self.focal_loss(pred, target)
        
        total = self.mse_weight * mse + self.focal_weight * focal
        
        components = {
            'mse': mse.item(),
            'focal': focal.item(),
            'total': total.item()
        }
        
        return total, components


def get_loss_function(loss_name: str = 'combined', **kwargs):
    """
    Factory function to get loss function by name.
    
    Args:
        loss_name: Name of the loss function
        **kwargs: Additional arguments for the loss function
    
    Returns:
        Loss function instance
    """
    loss_functions = {
        'mse': WeightedMSELoss(**kwargs),
        'combined': CombinedLoss(**kwargs),
        'logcosh': LogcoshLoss(),
        'heavy_rain': HeavyRainfallLoss(**kwargs)
    }
    
    if loss_name not in loss_functions:
        raise ValueError(
            f"Unknown loss function: {loss_name}. "
            f"Available: {list(loss_functions.keys())}"
        )
    
    return loss_functions[loss_name]


if __name__ == "__main__":
    # Test loss functions
    batch_size = 4
    T_out = 6
    height, width = 81, 81
    
    pred = torch.randn(batch_size, T_out, 1, height, width).abs()
    target = torch.randn(batch_size, T_out, 1, height, width).abs()
    
    # Test each loss
    losses = {
        'Weighted MSE': WeightedMSELoss(),
        'Combined Loss': CombinedLoss(),
        'Logcosh': LogcoshLoss(),
        'Heavy Rainfall': HeavyRainfallLoss()
    }
    
    for name, loss_fn in losses.items():
        if hasattr(loss_fn, 'forward') and 'components' in str(loss_fn.forward.__code__.co_varnames):
            l, comps = loss_fn(pred, target)
            print(f"{name}: {comps}")
        else:
            l = loss_fn(pred, target)
            print(f"{name}: {l.item():.6f}")
