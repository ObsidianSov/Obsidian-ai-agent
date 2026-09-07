"""
Osogbo RainCast AI - ConvLSTM Cell Implementation

This module implements the ConvLSTM cell as described in:
"Convolutional LSTM Network: A Machine Learning Approach for Precipitation Nowcasting"
(Shi et al., 2015)

Author: Ahmad Suleiman
Institution: Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria
"""

import torch
import torch.nn as nn
from typing import Tuple, Optional


class ConvLSTMCell(nn.Module):
    """
    Convolutional LSTM Cell
    
    Extends the standard LSTM to handle 2D spatial data by replacing
    matrix multiplications with 2D convolutions.
    
    Args:
        input_channels (int): Number of input channels
        hidden_channels (int): Number of hidden channels
        kernel_size (int): Size of the convolutional kernel (default: 3)
        bias (bool): Whether to include bias terms (default: True)
    
    Input:
        x_t: Input tensor at time t, shape (B, C_in, H, W)
        h_prev: Previous hidden state, shape (B, C_hidden, H, W)
        c_prev: Previous cell state, shape (B, C_hidden, H, W)
    
    Output:
        h_next: Next hidden state, shape (B, C_hidden, H, W)
        c_next: Next cell state, shape (B, C_hidden, H, W)
    
    Example:
        >>> cell = ConvLSTMCell(input_channels=64, hidden_channels=128)
        >>> h, c = cell(x, h_prev, c_prev)
    """
    
    def __init__(
        self, 
        input_channels: int, 
        hidden_channels: int, 
        kernel_size: int = 3,
        bias: bool = True
    ):
        super(ConvLSTMCell, self).__init__()
        
        self.input_channels = input_channels
        self.hidden_channels = hidden_channels
        self.kernel_size = kernel_size
        self.bias = bias
        
        # Padding to maintain spatial dimensions
        padding = kernel_size // 2
        
        # Input-to-hidden convolutions
        self.W_xi = nn.Conv2d(
            in_channels=input_channels, 
            out_channels=hidden_channels, 
            kernel_size=kernel_size, 
            padding=padding, 
            bias=bias
        )
        self.W_xf = nn.Conv2d(
            in_channels=input_channels, 
            out_channels=hidden_channels, 
            kernel_size=kernel_size, 
            padding=padding, 
            bias=bias
        )
        self.W_xg = nn.Conv2d(
            in_channels=input_channels, 
            out_channels=hidden_channels, 
            kernel_size=kernel_size, 
            padding=padding, 
            bias=bias
        )
        self.W_xo = nn.Conv2d(
            in_channels=input_channels, 
            out_channels=hidden_channels, 
            kernel_size=kernel_size, 
            padding=padding, 
            bias=bias
        )
        
        # Hidden-to-hidden convolutions
        self.W_hi = nn.Conv2d(
            in_channels=hidden_channels, 
            out_channels=hidden_channels, 
            kernel_size=kernel_size, 
            padding=padding, 
            bias=bias
        )
        self.W_hf = nn.Conv2d(
            in_channels=hidden_channels, 
            out_channels=hidden_channels, 
            kernel_size=kernel_size, 
            padding=padding, 
            bias=bias
        )
        self.W_hg = nn.Conv2d(
            in_channels=hidden_channels, 
            out_channels=hidden_channels, 
            kernel_size=kernel_size, 
            padding=padding, 
            bias=bias
        )
        self.W_ho = nn.Conv2d(
            in_channels=hidden_channels, 
            out_channels=hidden_channels, 
            kernel_size=kernel_size, 
            padding=padding, 
            bias=bias
        )
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights using Xavier/Glorot initialization."""
        for module in self.children():
            if isinstance(module, nn.Conv2d):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
    
    def forward(
        self, 
        x: torch.Tensor, 
        h: Optional[torch.Tensor] = None, 
        c: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass of ConvLSTM cell.
        
        Args:
            x: Input tensor (B, C_in, H, W)
            h: Previous hidden state (B, C_hidden, H, W) or None
            c: Previous cell state (B, C_hidden, H, W) or None
        
        Returns:
            Tuple of (h_next, c_next)
        """
        batch, _, height, width = x.shape
        
        # Initialize hidden and cell states if not provided
        if h is None:
            h = torch.zeros(
                batch, self.hidden_channels, height, width,
                device=x.device, dtype=x.dtype
            )
        if c is None:
            c = torch.zeros(
                batch, self.hidden_channels, height, width,
                device=x.device, dtype=x.dtype
            )
        
        # Compute gates
        # Input gate
        i = torch.sigmoid(self.W_xi(x) + self.W_hi(h))
        
        # Forget gate
        f = torch.sigmoid(self.W_xf(x) + self.W_hf(h))
        
        # Cell candidate
        g = torch.tanh(self.W_xg(x) + self.W_hg(h))
        
        # Output gate
        o = torch.sigmoid(self.W_xo(x) + self.W_ho(h))
        
        # Update cell state
        c_next = f * c + i * g
        
        # Compute hidden state
        h_next = o * torch.tanh(c_next)
        
        return h_next, c_next


class ConvLSTMLayer(nn.Module):
    """
    Multi-step ConvLSTM Layer
    
    Processes a sequence of inputs through ConvLSTM cells.
    
    Args:
        input_channels (int): Number of input channels
        hidden_channels (int): Number of hidden channels
        kernel_size (int): Size of convolutional kernel
        num_layers (int): Number of ConvLSTM cells (default: 1)
        bias (bool): Whether to include bias terms
    """
    
    def __init__(
        self,
        input_channels: int,
        hidden_channels: int,
        kernel_size: int = 3,
        num_layers: int = 1,
        bias: bool = True
    ):
        super(ConvLSTMLayer, self).__init__()
        
        self.input_channels = input_channels
        self.hidden_channels = hidden_channels
        self.num_layers = num_layers
        
        # Create multiple ConvLSTM cells
        cells = []
        in_ch = input_channels
        for i in range(num_layers):
            cells.append(
                ConvLSTMCell(
                    input_channels=in_ch,
                    hidden_channels=hidden_channels,
                    kernel_size=kernel_size,
                    bias=bias
                )
            )
            in_ch = hidden_channels
        
        self.cells = nn.ModuleList(cells)
    
    def forward(
        self, 
        x: torch.Tensor,
        states: Optional[list] = None
    ) -> Tuple[torch.Tensor, list]:
        """
        Forward pass through the ConvLSTM layer.
        
        Args:
            x: Input sequence (B, T, C, H, W)
            states: List of (h, c) tuples for each layer, or None
        
        Returns:
            outputs: Output sequence (B, T, C_hidden, H, W)
            final_states: List of final (h, c) tuples
        """
        B, T, C, H, W = x.shape
        
        # Initialize states if not provided
        if states is None:
            states = [None] * self.num_layers
        
        outputs = []
        current_states = []
        
        for t in range(T):
            x_t = x[:, t, :, :, :]  # (B, C, H, W)
            
            for layer_idx, cell in enumerate(self.cells):
                h, c = cell(x_t, *states[layer_idx] if states[layer_idx] else (None, None))
                x_t = h
                
                if t == T - 1:
                    current_states.append((h, c))
            
            outputs.append(h)
        
        # Stack outputs: (B, T, C_hidden, H, W)
        outputs = torch.stack(outputs, dim=1)
        
        return outputs, current_states


# Test function
if __name__ == "__main__":
    # Quick test
    batch_size = 4
    seq_len = 12
    channels = 64
    height, width = 81, 81
    
    # Create cell
    cell = ConvLSTMCell(input_channels=channels, hidden_channels=128)
    
    # Test forward pass
    x = torch.randn(batch_size, channels, height, width)
    h, c = cell(x)
    
    print(f"Input shape: {x.shape}")
    print(f"Hidden state shape: {h.shape}")
    print(f"Cell state shape: {c.shape}")
    
    # Test layer
    layer = ConvLSTMLayer(input_channels=64, hidden_channels=128, num_layers=2)
    x_seq = torch.randn(batch_size, seq_len, channels, height, width)
    outputs, states = layer(x_seq)
    
    print(f"\nLayer input shape: {x_seq.shape}")
    print(f"Layer output shape: {outputs.shape}")
    print(f"Number of final states: {len(states)}")
