"""
Osogbo RainCast AI - Evaluation Metrics

This module implements evaluation metrics for rainfall nowcasting,
including RMSE, MAE, correlation, and categorical metrics (POD, FAR, CSI).

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
"""

import torch
import numpy as np
from typing import Dict, Tuple, Optional
from scipy.stats import pearsonr


def compute_rmse(pred: torch.Tensor, target: torch.Tensor) -> float:
    """
    Compute Root Mean Squared Error.
    
    Args:
        pred: Predictions (flattened)
        target: Ground truth (flattened)
    
    Returns:
        RMSE value
    """
    return torch.sqrt(torch.mean((pred - target) ** 2)).item()


def compute_mae(pred: torch.Tensor, target: torch.Tensor) -> float:
    """
    Compute Mean Absolute Error.
    
    Args:
        pred: Predictions (flattened)
        target: Ground truth (flattened)
    
    Returns:
        MAE value
    """
    return torch.mean(torch.abs(pred - target)).item()


def compute_mse(pred: torch.Tensor, target: torch.Tensor) -> float:
    """
    Compute Mean Squared Error.
    
    Args:
        pred: Predictions (flattened)
        target: Ground truth (flattened)
    
    Returns:
        MSE value
    """
    return torch.mean((pred - target) ** 2).item()


def compute_correlation(pred: torch.Tensor, target: torch.Tensor) -> float:
    """
    Compute Pearson correlation coefficient.
    
    Args:
        pred: Predictions
        target: Ground truth
    
    Returns:
        Correlation coefficient
    """
    pred_np = pred.flatten().cpu().numpy()
    target_np = target.flatten().cpu().numpy()
    
    if np.std(pred_np) == 0 or np.std(target_np) == 0:
        return 0.0
    
    corr, _ = pearsonr(pred_np, target_np)
    return corr if not np.isnan(corr) else 0.0


def compute_bias(pred: torch.Tensor, target: torch.Tensor) -> float:
    """
    Compute mean bias (pred - target).
    
    Args:
        pred: Predictions
        target: Ground truth
    
    Returns:
        Mean bias
    """
    return (pred - target).mean().item()


def compute_pod(pred: torch.Tensor, target: torch.Tensor, threshold: float) -> float:
    """
    Probability of Detection (Hit Rate)
    
    POD = Hits / (Hits + Misses)
    
    Args:
        pred: Predictions
        target: Ground truth
        threshold: Rainfall threshold (mm/h)
    
    Returns:
        POD value (0-1)
    """
    pred_binary = (pred >= threshold).float()
    target_binary = (target >= threshold).float()
    
    hits = (pred_binary * target_binary).sum()
    misses = ((1 - pred_binary) * target_binary).sum()
    
    total = hits + misses
    if total == 0:
        return 0.0
    
    return (hits / total).item()


def compute_far(pred: torch.Tensor, target: torch.Tensor, threshold: float) -> float:
    """
    False Alarm Ratio
    
    FAR = False Alarms / (Hits + False Alarms)
    
    Args:
        pred: Predictions
        target: Ground truth
        threshold: Rainfall threshold (mm/h)
    
    Returns:
        FAR value (0-1)
    """
    pred_binary = (pred >= threshold).float()
    target_binary = (target >= threshold).float()
    
    hits = (pred_binary * target_binary).sum()
    false_alarms = (pred_binary * (1 - target_binary)).sum()
    
    total = hits + false_alarms
    if total == 0:
        return 0.0
    
    return (false_alarms / total).item()


def compute_csi(pred: torch.Tensor, target: torch.Tensor, threshold: float) -> float:
    """
    Critical Success Index (Threat Score)
    
    CSI = Hits / (Hits + Misses + False Alarms)
    
    Args:
        pred: Predictions
        target: Ground truth
        threshold: Rainfall threshold (mm/h)
    
    Returns:
        CSI value (0-1)
    """
    pred_binary = (pred >= threshold).float()
    target_binary = (target >= threshold).float()
    
    hits = (pred_binary * target_binary).sum()
    misses = ((1 - pred_binary) * target_binary).sum()
    false_alarms = (pred_binary * (1 - target_binary)).sum()
    
    total = hits + misses + false_alarms
    if total == 0:
        return 0.0
    
    return (hits / total).item()


def computeETS(pred: torch.Tensor, target: torch.Tensor, threshold: float) -> float:
    """
    Equitable Threat Score (Gerrity Score)
    
    ETS = (Hits - Hits_random) / (Hits + Misses + False Alarms - Hits_random)
    
    where Hits_random = (Hits + Misses) * (Hits + False Alarms) / Total
    
    Args:
        pred: Predictions
        target: Ground truth
        threshold: Rainfall threshold (mm/h)
    
    Returns:
        ETS value (-1/3 to 1)
    """
    pred_binary = (pred >= threshold).float()
    target_binary = (target >= threshold).float()
    
    hits = (pred_binary * target_binary).sum().item()
    misses = ((1 - pred_binary) * target_binary).sum().item()
    false_alarms = (pred_binary * (1 - target_binary)).sum().item()
    correct_negatives = ((1 - pred_binary) * (1 - target_binary)).sum().item()
    
    total = hits + misses + false_alarms + correct_negatives
    
    if total == 0:
        return 0.0
    
    # Random hits
    hits_random = (hits + misses) * (hits + false_alarms) / total
    
    numerator = hits - hits_random
    denominator = hits + misses + false_alarms - hits_random
    
    if denominator == 0:
        return 0.0
    
    return numerator / denominator


def compute_persistence_score(
    pred: torch.Tensor, 
    target: torch.Tensor
) -> Tuple[float, float]:
    """
    Compute skill score relative to persistence forecast.
    
    Persistence = last observed value repeated for all forecast hours.
    
    Args:
        pred: Model predictions
        target: Ground truth
    
    Returns:
        Tuple of (mse_improvement, mae_improvement) over persistence
    """
    # Get last time step of target as persistence forecast
    if pred.dim() == 5:  # (B, T, C, H, W)
        persistence = target[:, -1:, :, :, :].expand_as(pred)
    else:
        persistence = target[-1:].expand_as(pred)
    
    # Compute MSE and MAE for persistence
    persistence_mse = torch.mean((persistence - target) ** 2).item()
    persistence_mae = torch.mean(torch.abs(persistence - target)).item()
    
    # Compute MSE and MAE for model
    model_mse = torch.mean((pred - target) ** 2).item()
    model_mae = torch.mean(torch.abs(pred - target)).item()
    
    # Skill score: positive = better than persistence
    if persistence_mse > 0:
        mse_skill = 1 - (model_mse / persistence_mse)
    else:
        mse_skill = 0.0
    
    if persistence_mae > 0:
        mae_skill = 1 - (model_mae / persistence_mae)
    else:
        mae_skill = 0.0
    
    return mse_skill, mae_skill


def compute_all_metrics(
    pred: torch.Tensor,
    target: torch.Tensor,
    thresholds: list = [1.0, 5.0, 10.0]
) -> Dict[str, float]:
    """
    Compute all evaluation metrics.
    
    Args:
        pred: Predictions tensor
        target: Ground truth tensor
        thresholds: List of rainfall thresholds
    
    Returns:
        Dictionary of all metrics
    """
    metrics = {}
    
    # Flatten tensors for point-wise metrics
    pred_flat = pred.flatten()
    target_flat = target.flatten()
    
    # Basic metrics
    metrics['rmse'] = compute_rmse(pred_flat, target_flat)
    metrics['mae'] = compute_mae(pred_flat, target_flat)
    metrics['mse'] = compute_mse(pred_flat, target_flat)
    metrics['correlation'] = compute_correlation(pred_flat, target_flat)
    metrics['bias'] = compute_bias(pred_flat, target_flat)
    
    # Per-hour metrics (if multi-step forecast)
    if pred.dim() == 5:
        for t in range(pred.shape[1]):
            pred_t = pred[:, t, :, :, :].flatten()
            target_t = target[:, t, :, :, :].flatten()
            metrics[f'rmse_h{t+1}'] = compute_rmse(pred_t, target_t)
            metrics[f'mae_h{t+1}'] = compute_mae(pred_t, target_t)
    
    # Threshold-based metrics
    for thresh in thresholds:
        metrics[f'pod_{thresh}'] = compute_pod(pred, target, thresh)
        metrics[f'far_{thresh}'] = compute_far(pred, target, thresh)
        metrics[f'csi_{thresh}'] = compute_csi(pred, target, thresh)
        metrics[f'ets_{thresh}'] = computeETS(pred, target, thresh)
    
    # Skill scores
    mse_skill, mae_skill = compute_persistence_score(pred, target)
    metrics['persistence_mse_skill'] = mse_skill
    metrics['persistence_mae_skill'] = mae_skill
    
    # Clamp values to valid ranges
    for key in ['pod', 'far', 'csi', 'ets']:
        for k in list(metrics.keys()):
            if k.startswith(key) and '_skill' not in k:
                metrics[k] = max(0.0, min(1.0, metrics[k]))
    
    return metrics


class MetricsTracker:
    """
    Track and aggregate metrics over training/evaluation.
    """
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all tracked metrics."""
        self.metrics = {}
        self.counts = {}
    
    def update(self, metrics: Dict[str, float], batch_size: int = 1):
        """Update metrics with new batch."""
        for key, value in metrics.items():
            if key not in self.metrics:
                self.metrics[key] = 0.0
                self.counts[key] = 0
            
            self.metrics[key] += value * batch_size
            self.counts[key] += batch_size
    
    def compute(self) -> Dict[str, float]:
        """Compute average metrics."""
        avg_metrics = {}
        for key in self.metrics:
            if self.counts[key] > 0:
                avg_metrics[key] = self.metrics[key] / self.counts[key]
        return avg_metrics
    
    def get_summary(self) -> str:
        """Get formatted summary of metrics."""
        metrics = self.compute()
        lines = []
        for key, value in sorted(metrics.items()):
            if 'pod' in key or 'far' in key or 'csi' in key or 'ets' in key:
                lines.append(f"  {key}: {value:.3f}")
            elif 'skill' in key:
                sign = '+' if value >= 0 else ''
                lines.append(f"  {key}: {sign}{value:.3f}")
            else:
                lines.append(f"  {key}: {value:.4f}")
        return '\n'.join(lines)


if __name__ == "__main__":
    # Test metrics
    print("Testing evaluation metrics...")
    
    batch_size = 4
    T_out = 6
    H, W = 81, 81
    
    pred = torch.randn(batch_size, T_out, 1, H, W).abs()
    target = torch.randn(batch_size, T_out, 1, H, W).abs()
    
    metrics = compute_all_metrics(pred, target, thresholds=[1.0, 5.0, 10.0])
    
    print("\nComputed Metrics:")
    for key, value in sorted(metrics.items()):
        if 'pod' in key or 'far' in key or 'csi' in key:
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value:.4f}")
    
    print("\n✅ Metrics test passed!")
