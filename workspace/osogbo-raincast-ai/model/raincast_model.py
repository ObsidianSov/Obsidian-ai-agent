"""
Osogbo RainCast AI - RainCastConvLSTM Model

This module implements the complete RainCastConvLSTM architecture for
rainfall nowcasting, consisting of:
- CNN Encoder: Compresses multivariate input features
- ConvLSTM Stack: Captures spatiotemporal dynamics
- CNN Decoder: Reconstructs rainfall fields at full resolution

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
"""

import torch
import torch.nn as nn
from typing import Tuple, Optional, List
from .convlstm_cell import ConvLSTMCell


class CNNEncoder(nn.Module):
    """
    CNN Encoder for multivariate input compression
    
    Compresses input features at each time step using a series of
    convolutional blocks. The encoder reduces spatial resolution
    while increasing feature channels.
    
    Architecture:
        Input: (B, C_in, H, W)
        ConvBlock1: Conv2d(C_in → 32) → Conv2d(32 → 32)
        ConvBlock2: Conv2d(32 → 64, stride=2) → Conv2d(64 → 64)
        Output: (B, 64, H/2, W/2)
    
    Args:
        C_in: Number of input channels
        C_out: Number of output channels (default: 64)
    """
    
    def __init__(self, C_in: int, C_out: int = 64):
        super(CNNEncoder, self).__init__()
        
        # ConvBlock1: No spatial reduction
        self.block1 = nn.Sequential(
            nn.Conv2d(C_in, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True)
        )
        
        # ConvBlock2: Reduces spatial size by 2
        self.block2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True)
        )
        
        # Output projection to match desired output channels
        if C_out != 64:
            self.projection = nn.Conv2d(64, C_out, kernel_size=1)
        else:
            self.projection = nn.Identity()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through encoder.
        
        Args:
            x: Input tensor (B, C_in, H, W)
        
        Returns:
            Encoded features (B, C_out, H/2, W/2)
        """
        x = self.block1(x)
        x = self.block2(x)
        x = self.projection(x)
        return x


class ConvLSTMStack(nn.Module):
    """
    ConvLSTM Stack for temporal modeling
    
    Processes the sequence of encoded features through multiple
    ConvLSTM layers to capture spatiotemporal dependencies.
    
    Args:
        input_channels: Number of input channels
        hidden_channels: Number of hidden channels per layer
        num_layers: Number of ConvLSTM layers
        kernel_size: Size of convolutional kernel
    """
    
    def __init__(
        self,
        input_channels: int,
        hidden_channels: int = 64,
        num_layers: int = 2,
        kernel_size: int = 3
    ):
        super(ConvLSTMStack, self).__init__()
        
        self.num_layers = num_layers
        self.hidden_channels = hidden_channels
        
        # Create ConvLSTM layers
        self.layers = nn.ModuleList()
        in_ch = input_channels
        
        for i in range(num_layers):
            self.layers.append(
                ConvLSTMCell(
                    input_channels=in_ch,
                    hidden_channels=hidden_channels,
                    kernel_size=kernel_size
                )
            )
            in_ch = hidden_channels
    
    def forward(
        self, 
        x: torch.Tensor,
        states: Optional[List[Tuple[torch.Tensor, torch.Tensor]]] = None
    ) -> Tuple[torch.Tensor, List[Tuple[torch.Tensor, torch.Tensor]]]:
        """
        Forward pass through ConvLSTM stack.
        
        Args:
            x: Input sequence (B, T, C, H, W)
            states: Initial states for each layer, or None
        
        Returns:
            outputs: Output sequence (B, T, C_hidden, H, W)
            final_states: Final hidden/cell states for each layer
        """
        B, T, C, H, W = x.shape
        
        # Initialize states if not provided
        if states is None:
            states = [None] * self.num_layers
        
        outputs = []
        current_states = []
        
        for t in range(T):
            x_t = x[:, t, :, :, :]  # (B, C, H, W)
            
            for layer_idx, cell in enumerate(self.layers):
                h, c = cell(
                    x_t,
                    *states[layer_idx] if states[layer_idx] else (None, None)
                )
                x_t = h
            
            outputs.append(h)
            
            # Store final states
            if t == T - 1:
                for layer_idx, cell in enumerate(self.layers):
                    # Re-run to get final states for each layer
                    current_input = x[:, t, :, :, :]
                    for li, cl in enumerate(self.layers):
                        h_l, c_l = cl(
                            current_input,
                            *states[li] if states[li] else (None, None)
                        )
                        if li == layer_idx:
                            current_states.append((h_l, c_l))
                        current_input = h_l
        
        # Stack outputs: (B, T, C_hidden, H, W)
        outputs = torch.stack(outputs, dim=1)
        
        return outputs, current_states
    
    def init_hidden(
        self, 
        batch_size: int, 
        height: int, 
        width: int, 
        device: torch.device
    ) -> List[Tuple[torch.Tensor, torch.Tensor]]:
        """Initialize hidden states for all layers."""
        states = []
        for _ in range(self.num_layers):
            h = torch.zeros(
                batch_size, self.hidden_channels, height, width,
                device=device
            )
            c = torch.zeros(
                batch_size, self.hidden_channels, height, width,
                device=device
            )
            states.append((h, c))
        return states


class CNNDecoder(nn.Module):
    """
    CNN Decoder for rainfall field reconstruction
    
    Takes the temporal representation from ConvLSTM and reconstructs
    rainfall fields at full spatial resolution.
    
    Architecture:
        Input: (B, C_hidden, H_enc, W_enc) - final hidden state
        UpsampleBlock1: Conv2d(C_hidden → 64) → ConvTranspose2d(64 → 32)
        UpsampleBlock2: Conv2d(32 → 32) → Conv2d(32 → 16)
        OutputHead: Conv2d(16 → T_out)
        Output: (B, T_out, 1, H, W)
    
    Args:
        C_hidden: Number of hidden channels
        T_out: Number of forecast hours
        H, W: Target spatial dimensions
    """
    
    def __init__(
        self,
        C_hidden: int = 64,
        T_out: int = 6,
        H: int = 81,
        W: int = 81
    ):
        super(CNNDecoder, self).__init__()
        
        self.T_out = T_out
        self.H = H
        self.W = W
        
        # UpsampleBlock1: Upsample to full resolution
        self.up_block1 = nn.Sequential(
            nn.Conv2d(C_hidden, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(64, 32, kernel_size=4, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True)
        )
        
        # UpsampleBlock2: Refine features
        self.up_block2 = nn.Sequential(
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True)
        )
        
        # Output head: Generate T_out frames
        self.output_head = nn.Conv2d(16, T_out, kernel_size=1)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through decoder.
        
        Args:
            x: Hidden state from ConvLSTM (B, C_hidden, H_enc, W_enc)
        
        Returns:
            Predicted rainfall fields (B, T_out, 1, H, W)
        """
        # UpsampleBlock1
        x = self.up_block1(x)  # (B, 32, H, W)
        
        # UpsampleBlock2
        x = self.up_block2(x)  # (B, 16, H, W)
        
        # Output head
        x = self.output_head(x)  # (B, T_out, H, W)
        
        # Reshape to (B, T_out, 1, H, W)
        B = x.shape[0]
        x = x.view(B, self.T_out, 1, self.H, self.W)
        
        return x


class RainCastConvLSTM(nn.Module):
    """
    RainCastConvLSTM: End-to-End Rainfall Nowcasting Model
    
    Complete model architecture:
    1. CNN Encoder: Compresses multivariate input at each time step
    2. ConvLSTM Stack: Captures spatiotemporal dynamics
    3. CNN Decoder: Reconstructs rainfall fields for forecast hours
    
    Args:
        C_in: Number of input channels (ERA5 variables)
        C_hidden: Number of hidden channels (default: 64)
        T_in: Input sequence length (default: 12 hours)
        T_out: Forecast horizon (default: 6 hours)
        H: Grid height (default: 81)
        W: Grid width (default: 81)
    
    Input:
        x: (B, T_in, C_in, H, W) - Input sequence of meteorological fields
    
    Output:
        pred: (B, T_out, 1, H, W) - Predicted rainfall for next T_out hours
    
    Example:
        >>> model = RainCastConvLSTM(C_in=8, C_hidden=64, T_in=12, T_out=6)
        >>> x = torch.randn(4, 12, 8, 81, 81)
        >>> pred = model(x)  # (4, 6, 1, 81, 81)
    """
    
    def __init__(
        self,
        C_in: int = 8,
        C_hidden: int = 64,
        T_in: int = 12,
        T_out: int = 6,
        H: int = 81,
        W: int = 81
    ):
        super(RainCastConvLSTM, self).__init__()
        
        self.C_in = C_in
        self.C_hidden = C_hidden
        self.T_in = T_in
        self.T_out = T_out
        self.H = H
        self.W = W
        
        # CNN Encoder (time-distributed)
        self.encoder = CNNEncoder(C_in=C_in, C_out=C_hidden)
        
        # ConvLSTM Stack
        self.convlstm = ConvLSTMStack(
            input_channels=C_hidden,
            hidden_channels=C_hidden,
            num_layers=2,
            kernel_size=3
        )
        
        # CNN Decoder
        # Calculate encoded spatial size (H/2, W/2)
        self.decoder = CNNDecoder(
            C_hidden=C_hidden,
            T_out=T_out,
            H=H // 2,  # Decoder upsamples back to original
            W=W // 2
        )
        
        # Store original H, W for final output
        self._orig_H = H
        self._orig_W = W
        
        # Upsampler if needed (handles odd dimensions)
        self.final_upsample = None
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize model weights."""
        for module in self.modules():
            if isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode='fan_out', nonlinearity='relu')
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.BatchNorm2d):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the complete model.
        
        Args:
            x: Input tensor (B, T_in, C_in, H, W)
        
        Returns:
            pred: Predicted rainfall (B, T_out, 1, H, W)
        """
        B, T_in, C_in, H, W = x.shape
        
        # Encode each time step
        encoded = []
        for t in range(T_in):
            z_t = self.encoder(x[:, t, :, :, :])
            encoded.append(z_t)
        
        # Stack encoded features: (B, T_in, C_hidden, H/2, W/2)
        encoded = torch.stack(encoded, dim=1)
        
        # Process through ConvLSTM
        lstm_out, final_states = self.convlstm(encoded)
        
        # Use final hidden state for decoder
        # Take the last time step's hidden state
        final_hidden = lstm_out[:, -1, :, :, :]  # (B, C_hidden, H/2, W/2)
        
        # Decode to rainfall prediction
        pred = self.decoder(final_hidden)  # (B, T_out, 1, H/2, W/2)
        
        # Upsample to original resolution if needed
        if self._orig_H != H // 2 or self._orig_W != W // 2:
            pred = self._resize_output(pred)
        
        return pred
    
    def _resize_output(self, pred: torch.Tensor) -> torch.Tensor:
        """Resize output to original grid size."""
        B, T, C, H_enc, W_enc = pred.shape
        
        # Reshape for interpolation: (B*T, C, H, W)
        pred_flat = pred.view(B * T, C, H_enc, W_enc)
        
        # Interpolate to original size
        pred_resized = torch.nn.functional.interpolate(
            pred_flat,
            size=(self._orig_H, self._orig_W),
            mode='bilinear',
            align_corners=False
        )
        
        # Reshape back: (B, T, C, H, W)
        pred = pred_resized.view(B, T, C, self._orig_H, self._orig_W)
        
        return pred
    
    def get_num_parameters(self) -> int:
        """Get total number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
    
    def get_model_size_mb(self) -> float:
        """Get model size in megabytes."""
        param_size = 0
        for param in self.parameters():
            param_size += param.nelement() * param.element_size()
        buffer_size = 0
        for buffer in self.buffers():
            buffer_size += buffer.nelement() * buffer.element_size()
        size_mb = (param_size + buffer_size) / 1024 / 1024
        return size_mb


def create_model(config: dict) -> RainCastConvLSTM:
    """
    Factory function to create model from config.
    
    Args:
        config: Dictionary with model configuration
    
    Returns:
        RainCastConvLSTM model instance
    """
    model = RainCastConvLSTM(
        C_in=config.get('C_in', 8),
        C_hidden=config.get('C_hidden', 64),
        T_in=config.get('T_in', 12),
        T_out=config.get('T_out', 6),
        H=config.get('H', 81),
        W=config.get('W', 81)
    )
    return model


# Test function
if __name__ == "__main__":
    # Test the model
    print("Testing RainCastConvLSTM model...")
    
    # Create model
    model = RainCastConvLSTM(C_in=8, C_hidden=64, T_in=12, T_out=6)
    
    # Print model info
    print(f"\nModel Parameters: {model.get_num_parameters():,}")
    print(f"Model Size: {model.get_model_size_mb():.2f} MB")
    
    # Test forward pass
    batch_size = 2
    x = torch.randn(batch_size, 12, 8, 81, 81)
    
    with torch.no_grad():
        pred = model(x)
    
    print(f"\nInput shape: {x.shape}")
    print(f"Output shape: {pred.shape}")
    
    # Check output range
    print(f"\nPrediction range: [{pred.min():.4f}, {pred.max():.4f}]")
    print(f"Prediction mean: {pred.mean():.4f}")
    
    print("\n✅ Model test passed!")
