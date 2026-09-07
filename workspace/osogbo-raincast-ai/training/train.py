"""
Osogbo RainCast AI - Training Script

This script handles the complete training pipeline for the RainCastConvLSTM model,
including:
- Configuration loading
- Data loading
- Model initialization
- Training loop with validation
- Checkpointing and logging
- Early stopping

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

import torch
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter
from torch.optim import Adam, AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, ReduceLROnPlateau, StepLR

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from model import RainCastConvLSTM, get_loss_function
from training.metrics import compute_all_metrics, MetricsTracker
from training.dataset import create_dataloaders


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Train RainCastConvLSTM model')
    parser.add_argument('--config', type=str, default='training/config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--resume', type=str, default=None,
                        help='Path to checkpoint to resume from')
    parser.add_argument('--device', type=str, default=None,
                        help='Device to use (cuda/cpu)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    return parser.parse_args()


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def setup_directories(config: Dict):
    """Create necessary directories."""
    log_dir = Path(config['training']['log_dir'])
    checkpoint_dir = Path(config['training']['checkpoint_dir'])
    
    log_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    return log_dir, checkpoint_dir


def create_model(config: Dict, device: torch.device) -> nn.Module:
    """Create and initialize the model."""
    model = RainCastConvLSTM(
        C_in=config['model']['C_in'],
        C_hidden=config['model']['C_hidden'],
        T_in=config['model']['T_in'],
        T_out=config['model']['T_out'],
        H=config['model']['H'],
        W=config['model']['W']
    )
    
    model = model.to(device)
    
    return model


def create_optimizer(model: nn.Module, config: Dict):
    """Create optimizer based on config."""
    optimizer_name = config['training']['optimizer'].lower()
    lr = config['training']['learning_rate']
    weight_decay = config['training']['weight_decay']
    
    if optimizer_name == 'adam':
        optimizer = Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    elif optimizer_name == 'adamw':
        optimizer = AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    elif optimizer_name == 'sgd':
        optimizer = torch.optim.SGD(model.parameters(), lr=lr, 
                                     momentum=0.9, weight_decay=weight_decay)
    else:
        raise ValueError(f"Unknown optimizer: {optimizer_name}")
    
    return optimizer


def create_scheduler(optimizer, config: Dict):
    """Create learning rate scheduler."""
    scheduler_name = config['training']['scheduler'].lower()
    
    if scheduler_name == 'none':
        return None
    elif scheduler_name == 'cosine':
        scheduler = CosineAnnealingLR(
            optimizer, 
            T_max=config['training']['num_epochs']
        )
    elif scheduler_name == 'step':
        scheduler = StepLR(
            optimizer,
            step_size=config['training']['step_size'],
            gamma=config['training']['gamma']
        )
    elif scheduler_name == 'plateau':
        scheduler = ReduceLROnPlateau(
            optimizer,
            mode='min',
            factor=config['training']['gamma'],
            patience=5
        )
    else:
        raise ValueError(f"Unknown scheduler: {scheduler_name}")
    
    return scheduler


def train_epoch(
    model: nn.Module,
    train_loader,
    criterion,
    optimizer,
    device: torch.device,
    config: Dict,
    epoch: int,
    writer: SummaryWriter
) -> MetricsTracker:
    """Train for one epoch."""
    model.train()
    tracker = MetricsTracker()
    
    log_interval = config['training']['log_interval']
    use_amp = config['training']['use_amp']
    
    # Mixed precision scaler
    scaler = torch.cuda.amp.GradScaler() if use_amp else None
    
    for batch_idx, (X, Y) in enumerate(train_loader):
        X = X.to(device)
        Y = Y.to(device)
        
        optimizer.zero_grad()
        
        if use_amp:
            with torch.cuda.amp.autocast():
                pred = model(X)
                loss, loss_components = criterion(pred, Y)
            
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            
            # Gradient clipping
            if config['training']['clip_grad_norm'] > 0:
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(), 
                    config['training']['clip_grad_norm']
                )
            
            scaler.step(optimizer)
            scaler.update()
        else:
            pred = model(X)
            loss, loss_components = criterion(pred, Y)
            loss.backward()
            
            if config['training']['clip_grad_norm'] > 0:
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(),
                    config['training']['clip_grad_norm']
                )
            
            optimizer.step()
        
        # Compute metrics
        with torch.no_grad():
            metrics = compute_all_metrics(pred, Y)
            metrics['loss'] = loss.item()
            metrics.update(loss_components)
        
        tracker.update(metrics, batch_size=X.shape[0])
        
        # Logging
        if batch_idx % log_interval == 0:
            print(f"  Batch {batch_idx}/{len(train_loader)} | "
                  f"Loss: {loss.item():.4f} | "
                  f"RMSE: {metrics['rmse']:.4f}")
    
    return tracker


def validate(
    model: nn.Module,
    val_loader,
    criterion,
    device: torch.device
) -> MetricsTracker:
    """Validate the model."""
    model.eval()
    tracker = MetricsTracker()
    
    with torch.no_grad():
        for X, Y in val_loader:
            X = X.to(device)
            Y = Y.to(device)
            
            pred = model(X)
            loss, loss_components = criterion(pred, Y)
            
            metrics = compute_all_metrics(pred, Y)
            metrics['loss'] = loss.item()
            metrics.update(loss_components)
            
            tracker.update(metrics, batch_size=X.shape[0])
    
    return tracker


def save_checkpoint(
    model: nn.Module,
    optimizer,
    scheduler,
    epoch: int,
    metrics: Dict,
    checkpoint_dir: Path,
    is_best: bool = False
):
    """Save model checkpoint."""
    checkpoint = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'metrics': metrics
    }
    
    if scheduler is not None:
        checkpoint['scheduler_state_dict'] = scheduler.state_dict()
    
    # Save latest checkpoint
    latest_path = checkpoint_dir / 'latest.pt'
    torch.save(checkpoint, latest_path)
    
    # Save epoch checkpoint
    epoch_path = checkpoint_dir / f'epoch_{epoch:03d}.pt'
    torch.save(checkpoint, epoch_path)
    
    # Save best checkpoint
    if is_best:
        best_path = checkpoint_dir / 'best.pt'
        torch.save(checkpoint, best_path)
        print(f"  ✓ Saved best model to {best_path}")


def main():
    """Main training function."""
    args = parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Setup
    log_dir, checkpoint_dir = setup_directories(config)
    
    # Device
    if args.device:
        device = torch.device(args.device)
    else:
        device = torch.device(config['training']['device'])
    
    print("=" * 60)
    print("Osogbo RainCast AI - Model Training")
    print("=" * 60)
    print(f"Device: {device}")
    print(f"Log directory: {log_dir}")
    print(f"Checkpoint directory: {checkpoint_dir}")
    print()
    
    # Set random seed
    if config.get('seed'):
        torch.manual_seed(config['seed'])
        if torch.cuda.is_available():
            torch.cuda.manual_seed(config['seed'])
    
    # Create data loaders
    print("Loading data...")
    train_loader, val_loader, test_loader = create_dataloaders(config)
    print(f"Train batches: {len(train_loader)}")
    print(f"Val batches: {len(val_loader)}")
    print()
    
    # Create model
    print("Creating model...")
    model = create_model(config, device)
    print(f"Model parameters: {model.get_num_parameters():,}")
    print(f"Model size: {model.get_model_size_mb():.2f} MB")
    print()
    
    # Create loss function
    criterion = get_loss_function(
        loss_name=config['loss']['name'],
        mse_weight=config['loss'].get('mse_weight', 1.0),
        mae_weight=config['loss'].get('mae_weight', 0.1)
    )
    
    # Create optimizer and scheduler
    optimizer = create_optimizer(model, config)
    scheduler = create_scheduler(optimizer, config)
    
    # Resume from checkpoint if specified
    start_epoch = 0
    best_val_loss = float('inf')
    
    if args.resume:
        print(f"Resuming from checkpoint: {args.resume}")
        checkpoint = torch.load(args.resume, map_location=device)
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        start_epoch = checkpoint['epoch'] + 1
        best_val_loss = checkpoint['metrics'].get('val_loss', float('inf'))
        print(f"Resuming from epoch {start_epoch}")
        print()
    
    # TensorBoard writer
    writer = SummaryWriter(log_dir=log_dir)
    
    # Training loop
    print("Starting training...")
    print("-" * 60)
    
    patience_counter = 0
    num_epochs = config['training']['num_epochs']
    early_stopping_patience = config['training'].get('early_stopping_patience', 10)
    
    for epoch in range(start_epoch, num_epochs):
        print(f"\nEpoch {epoch + 1}/{num_epochs}")
        print("-" * 40)
        
        # Training
        train_tracker = train_epoch(
            model, train_loader, criterion, optimizer, device, config, epoch, writer
        )
        train_metrics = train_tracker.compute()
        
        # Validation
        val_tracker = validate(model, val_loader, criterion, device)
        val_metrics = val_tracker.compute()
        
        # Learning rate scheduling
        if scheduler is not None:
            if isinstance(scheduler, ReduceLROnPlateau):
                scheduler.step(val_metrics['loss'])
            else:
                scheduler.step()
        
        current_lr = optimizer.param_groups[0]['lr']
        
        # Print epoch summary
        print(f"\nEpoch {epoch + 1} Summary:")
        print(f"  Train Loss: {train_metrics['loss']:.4f} | Val Loss: {val_metrics['loss']:.4f}")
        print(f"  Train RMSE: {train_metrics['rmse']:.4f} | Val RMSE: {val_metrics['rmse']:.4f}")
        print(f"  Train MAE: {train_metrics['mae']:.4f} | Val MAE: {val_metrics['mae']:.4f}")
        print(f"  Correlation: {val_metrics['correlation']:.4f}")
        print(f"  Learning Rate: {current_lr:.6f}")
        
        # Log to TensorBoard
        for key, value in train_metrics.items():
            writer.add_scalar(f'train/{key}', value, epoch)
        for key, value in val_metrics.items():
            writer.add_scalar(f'val/{key}', value, epoch)
        writer.add_scalar('learning_rate', current_lr, epoch)
        
        # Checkpointing
        val_loss = val_metrics['loss']
        is_best = val_loss < best_val_loss
        
        if is_best:
            best_val_loss = val_loss
            patience_counter = 0
        else:
            patience_counter += 1
        
        # Save checkpoint
        if epoch % config['training']['save_interval'] == 0 or is_best:
            save_checkpoint(
                model, optimizer, scheduler, epoch,
                {'val_loss': val_loss, **val_metrics},
                checkpoint_dir,
                is_best=is_best
            )
        
        # Early stopping
        if patience_counter >= early_stopping_patience:
            print(f"\n⚠ Early stopping triggered after {epoch + 1} epochs")
            break
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print(f"Best validation loss: {best_val_loss:.4f}")
    print(f"Checkpoints saved to: {checkpoint_dir}")
    print("=" * 60)
    
    # Test evaluation
    print("\nRunning test evaluation...")
    test_tracker = validate(model, test_loader, criterion, device)
    test_metrics = test_tracker.compute()
    
    print("\nTest Metrics:")
    print(test_tracker.get_summary())
    
    # Save test metrics
    test_results_path = checkpoint_dir / 'test_results.json'
    with open(test_results_path, 'w') as f:
        json.dump(test_metrics, f, indent=2)
    print(f"\nTest results saved to: {test_results_path}")
    
    writer.close()


if __name__ == "__main__":
    main()
