"""
Autoencoder-based Novelty Detector

Uses a deep autoencoder to learn compressed representations of normal traffic.
Novel patterns have high reconstruction error.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import json
from pathlib import Path
from typing import Optional, List
import logging

from .detector import NoveltyDetector

logger = logging.getLogger(__name__)


class Autoencoder(nn.Module):
    """
    Deep autoencoder network for learning compressed representations.
    """
    
    def __init__(self, input_dim: int, encoding_dims: List[int] = None):
        """
        Args:
            input_dim: Number of input features
            encoding_dims: Hidden layer dimensions (encoder path)
                          Decoder mirrors these in reverse
                          Default: [64, 32, 16]
        """
        super().__init__()
        
        if encoding_dims is None:
            encoding_dims = [64, 32, 16]
        
        self.input_dim = input_dim
        self.encoding_dims = encoding_dims
        
        # Build encoder
        encoder_layers = []
        prev_dim = input_dim
        for dim in encoding_dims:
            encoder_layers.extend([
                nn.Linear(prev_dim, dim),
                nn.ReLU(),
                nn.BatchNorm1d(dim),
                nn.Dropout(0.2)
            ])
            prev_dim = dim
        
        self.encoder = nn.Sequential(*encoder_layers)
        
        # Build decoder (mirror of encoder)
        decoder_layers = []
        decoding_dims = list(reversed(encoding_dims[:-1])) + [input_dim]
        prev_dim = encoding_dims[-1]
        for i, dim in enumerate(decoding_dims):
            decoder_layers.append(nn.Linear(prev_dim, dim))
            if i < len(decoding_dims) - 1:  # No activation on output layer
                decoder_layers.extend([
                    nn.ReLU(),
                    nn.BatchNorm1d(dim),
                    nn.Dropout(0.2)
                ])
            prev_dim = dim
        
        self.decoder = nn.Sequential(*decoder_layers)
    
    def forward(self, x):
        """Forward pass through autoencoder."""
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded
    
    def encode(self, x):
        """Get compressed representation."""
        return self.encoder(x)


class AutoencoderDetector(NoveltyDetector):
    """
    Autoencoder-based novelty detector.
    
    Advantages:
    - Learns complex non-linear patterns
    - Can capture subtle differences in normal traffic
    - Provides interpretable reconstruction errors
    
    The detector learns to reconstruct normal traffic.
    Novel patterns have high reconstruction error.
    """
    
    def __init__(
        self,
        threshold: float = 0.5,
        encoding_dims: List[int] = None,
        learning_rate: float = 0.001,
        batch_size: int = 128,
        epochs: int = 50,
        device: str = None,
        **kwargs
    ):
        """
        Args:
            threshold: Novelty score threshold (0-1)
            encoding_dims: Hidden dimensions for encoder
            learning_rate: Adam optimizer learning rate
            batch_size: Training batch size
            epochs: Training epochs
            device: 'cuda', 'cpu', or None (auto-detect)
        """
        super().__init__(
            threshold=threshold,
            name="Autoencoder",
            **kwargs
        )
        
        self.encoding_dims = encoding_dims or [64, 32, 16]
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        
        # Set device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.model = None
        self.input_dim = None
        self.train_loss_history = []
        
        # For normalizing reconstruction errors to [0, 1]
        self.error_mean = None
        self.error_std = None
        
        logger.info(
            f"Initialized Autoencoder with encoding_dims={self.encoding_dims}, "
            f"device={self.device}"
        )
    
    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> 'AutoencoderDetector':
        """
        Train autoencoder on normal traffic patterns.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Ignored (unsupervised method)
            
        Returns:
            self
        """
        logger.info(f"Training Autoencoder on {len(X)} samples for {self.epochs} epochs...")
        
        # Initialize model
        self.input_dim = X.shape[1]
        self.model = Autoencoder(self.input_dim, self.encoding_dims).to(self.device)
        
        # Prepare data
        X_tensor = torch.FloatTensor(X)
        dataset = TensorDataset(X_tensor, X_tensor)  # Target = input for autoencoder
        dataloader = DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=True,
            drop_last=False
        )
        
        # Training setup
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)
        
        # Training loop
        self.model.train()
        for epoch in range(self.epochs):
            epoch_loss = 0.0
            for batch_X, batch_target in dataloader:
                batch_X = batch_X.to(self.device)
                batch_target = batch_target.to(self.device)
                
                # Forward pass
                reconstructed = self.model(batch_X)
                loss = criterion(reconstructed, batch_target)
                
                # Backward pass
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                epoch_loss += loss.item()
            
            avg_loss = epoch_loss / len(dataloader)
            self.train_loss_history.append(avg_loss)
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{self.epochs}, Loss: {avg_loss:.6f}")
        
        # Calculate error statistics on training data for normalization
        self.model.eval()
        with torch.no_grad():
            X_tensor = X_tensor.to(self.device)
            reconstructed = self.model(X_tensor)
            errors = torch.mean((X_tensor - reconstructed) ** 2, dim=1).cpu().numpy()
            
            self.error_mean = np.mean(errors)
            self.error_std = np.std(errors)
        
        self.is_fitted = True
        
        logger.info(
            f"Autoencoder training complete. Final loss: {self.train_loss_history[-1]:.6f}, "
            f"Reconstruction error - mean: {self.error_mean:.6f}, std: {self.error_std:.6f}"
        )
        
        return self
    
    def predict_novelty(self, X: np.ndarray) -> np.ndarray:
        """
        Predict novelty scores based on reconstruction error.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Novelty scores (n_samples,) in range [0, 1]
        """
        if not self.is_fitted:
            raise RuntimeError("Detector must be fitted before prediction")
        
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            reconstructed = self.model(X_tensor)
            
            # Calculate mean squared error per sample
            mse = torch.mean((X_tensor - reconstructed) ** 2, dim=1).cpu().numpy()
            
            # Normalize using training statistics
            # z-score normalization, then sigmoid to [0, 1]
            if self.error_std > 0:
                z_scores = (mse - self.error_mean) / self.error_std
            else:
                z_scores = mse - self.error_mean
            
            # Sigmoid transformation to [0, 1]
            scores = 1 / (1 + np.exp(-z_scores))
            
            return scores
    
    def save(self, path: str) -> None:
        """
        Save detector state to disk.
        
        Args:
            path: Directory path to save detector
        """
        save_dir = Path(path)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model weights
        model_path = save_dir / "autoencoder.pt"
        torch.save(self.model.state_dict(), model_path)
        
        # Save metadata
        metadata = {
            'name': self.name,
            'threshold': self.threshold,
            'encoding_dims': self.encoding_dims,
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'epochs': self.epochs,
            'input_dim': self.input_dim,
            'is_fitted': self.is_fitted,
            'samples_seen': self.samples_seen,
            'min_samples_fit': self.min_samples_fit,
            'error_mean': float(self.error_mean) if self.error_mean is not None else None,
            'error_std': float(self.error_std) if self.error_std is not None else None,
            'train_loss_history': self.train_loss_history
        }
        
        metadata_path = save_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Saved Autoencoder detector to {save_dir}")
    
    def load(self, path: str) -> 'AutoencoderDetector':
        """
        Load detector state from disk.
        
        Args:
            path: Directory path to load from
            
        Returns:
            self
        """
        load_dir = Path(path)
        
        # Load metadata
        metadata_path = load_dir / "metadata.json"
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Restore attributes
        self.threshold = metadata['threshold']
        self.encoding_dims = metadata['encoding_dims']
        self.learning_rate = metadata['learning_rate']
        self.batch_size = metadata['batch_size']
        self.epochs = metadata['epochs']
        self.input_dim = metadata['input_dim']
        self.is_fitted = metadata['is_fitted']
        self.samples_seen = metadata['samples_seen']
        self.min_samples_fit = metadata['min_samples_fit']
        self.error_mean = metadata['error_mean']
        self.error_std = metadata['error_std']
        self.train_loss_history = metadata['train_loss_history']
        
        # Rebuild model and load weights
        self.model = Autoencoder(self.input_dim, self.encoding_dims).to(self.device)
        model_path = load_dir / "autoencoder.pt"
        self.model.load_state_dict(torch.load(model_path, map_location=self.device, weights_only=True))
        self.model.eval()
        
        logger.info(f"Loaded Autoencoder detector from {load_dir}")
        
        return self
