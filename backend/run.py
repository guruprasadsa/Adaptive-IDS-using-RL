# -*- coding: utf-8 -*-
"""
adaptive_ids_rl.py

A single-file, self-contained Python script to train an Adaptive Intrusion 
Detection System (IDS) using Reinforcement Learning on the CSE-CIC-IDS2018 dataset.

This script is designed for Windows execution and leverages PyTorch 2.x for 
GPU-accelerated training with modern features like mixed precision and torch.compile.

Key Features:
- End-to-end pipeline: Data loading, preprocessing, training, and evaluation.
- Reinforcement Learning: Implements a Double DQN agent to adapt to threats.
- GPU Optimization: Auto-detects CUDA, uses mixed precision (AMP), and torch.compile.
- Preprocessing: Handles feature sanitization, scaling, and class imbalance.
- Configurable: Extensive command-line arguments to control the training process.
- Logging & Checkpointing: Saves progress, metrics, and models for reproducibility.
- Evaluation: Provides detailed performance metrics, including confusion matrices.

Execution Examples (Windows):
1. Train a binary classifier using Double DQN on a CUDA-enabled GPU:
   python adaptive_ids_rl.py --data-dir "C:\Data\CSE-CIC-IDS2018" --binary --device cuda --epochs 20 --batch-size 2048

2. Resume training from a checkpoint for a multi-class model:
   python adaptive_ids_rl.py --data-dir "C:\Data\CSE-CIC-IDS2018" --resume "C:\runs\IDS_run_1\best_model.pth"

3. Train with SMOTE for handling class imbalance:
   python adaptive_ids_rl.py --data-dir "C:\Data\CSE-CIC-IDS2018" --binary --use-smote
"""

import argparse
import os
import sys
import time
import json
import random
from datetime import datetime
from collections import deque, namedtuple
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torch.utils.tensorboard import SummaryWriter

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (accuracy_score, precision_recall_fscore_support,
                             confusion_matrix, roc_auc_score, classification_report)

# Suppress potential warnings from imblearn if it's used
try:
    from imblearn.over_sampling import SMOTE
    IMBLEARN_AVAILABLE = True
except ImportError:
    IMBLEARN_AVAILABLE = False
    
# Suppress pandas warnings about chained assignment
pd.options.mode.chained_assignment = None

# --- Utility Functions ---

def set_seed(seed_value=42):
    """Set seed for reproducibility."""
    random.seed(seed_value)
    np.random.seed(seed_value)
    torch.manual_seed(seed_value)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed_value)
        torch.cuda.manual_seed_all(seed_value)
        # The two lines below are known to cause issues with torch.compile
        # torch.backends.cudnn.deterministic = True
        # torch.backends.cudnn.benchmark = False

def clean_col_names(df):
    """Sanitize column names of a pandas DataFrame."""
    cols = df.columns
    new_cols = []
    for col in cols:
        new_col = col.strip().lower().replace(' ', '_').replace('-', '_')
        new_cols.append(new_col)
    df.columns = new_cols
    return df

# --- Data Loading and Preprocessing ---

class IntrusionDataset(Dataset):
    """PyTorch Dataset for the IDS data."""
    def __init__(self, features, labels):
        self.features = torch.tensor(features, dtype=torch.float32)
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]

def load_and_preprocess_data(data_dir, binary=True, use_smote=False, test_size=0.2, val_size=0.2):
    """
    Loads, preprocesses, and splits the CSE-CIC-IDS2018 dataset.
    """
    print(f"[*] Starting data loading from: {data_dir}")
    csv_files = list(Path(data_dir).rglob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}. Please check the --data-dir path.")

    df_list = []
    for file in csv_files:
        print(f"  - Loading {file.name}...")
        try:
            # Using low_memory=False can help with mixed type inference issues
            df_list.append(pd.read_csv(file, low_memory=False))
        except Exception as e:
            print(f"    Warning: Could not read {file.name}. Error: {e}")
            continue
    
    if not df_list:
        raise ValueError("Failed to load any data from the specified directory.")
        
    full_df = pd.concat(df_list, ignore_index=True)
    print(f"[*] Combined dataset shape: {full_df.shape}")

    # --- Preprocessing ---
    print("[*] Starting preprocessing...")
    full_df = clean_col_names(full_df)
    
    # Find label column
    label_col = None
    if 'label' in full_df.columns:
        label_col = 'label'
    else:
        # Handle potential variations if needed
        for col in full_df.columns:
            if 'label' in col:
                label_col = col
                break
    if label_col is None:
        raise ValueError("Could not find 'Label' column in the dataset.")

    # Drop non-predictive columns
    cols_to_drop = ['timestamp', 'dst_port'] 
    # dst_port is often categorical with too many values, dropping for simplicity
    # In a more advanced setup, this could be handled with embedding layers
    cols_to_drop_existing = [col for col in cols_to_drop if col in full_df.columns]
    full_df.drop(columns=cols_to_drop_existing, inplace=True)

    # Handle infinities and NaNs
    full_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    print(f"  - Found {full_df.isna().sum().sum()} NaN values. Filling with column median.")
    for col in full_df.select_dtypes(include=np.number).columns.tolist():
        if full_df[col].isnull().any():
            median_val = full_df[col].median()
            full_df[col].fillna(median_val, inplace=True)

    # Separate features and labels
    X = full_df.drop(columns=[label_col])
    y = full_df[label_col]

    # Convert all feature columns to numeric, coercing errors
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors='coerce')
    
    # Re-check for NaNs after coercion and fill
    if X.isna().sum().sum() > 0:
        print(f"  - Found {X.isna().sum().sum()} new NaNs after numeric coercion. Filling with median.")
        for col in X.columns:
            if X[col].isnull().any():
                X[col].fillna(X[col].median(), inplace=True)

    print(f"[*] Label processing (Binary mode: {binary})")
    if binary:
        y = y.apply(lambda x: 'Benign' if 'Benign' in x else 'Attack')
    
    # Encode labels
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    print(f"  - Label mapping: {dict(zip(le.classes_, le.transform(le.classes_)))}")
    
    # --- Data Splitting ---
    print("[*] Splitting data into train, validation, and test sets...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=test_size, random_state=42, stratify=y_encoded
    )
    
    # Adjust val_size to be a proportion of the remaining training data
    val_split_ratio = val_size / (1 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=val_split_ratio, random_state=42, stratify=y_train
    )

    print(f"  - Train set: {X_train.shape}, Val set: {X_val.shape}, Test set: {X_test.shape}")
    
    # --- Feature Scaling ---
    print("[*] Scaling features with StandardScaler...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)

    # --- Handle Class Imbalance (Optional) ---
    if use_smote:
        if not IMBLEARN_AVAILABLE:
            print("  - Warning: --use-smote was specified, but 'imblearn' is not installed. Skipping SMOTE.")
            print("  - To install: pip install -U scikit-learn imbalanced-learn")
        else:
            print("[*] Applying SMOTE to the training data...")
            smote = SMOTE(random_state=42)
            X_train_scaled, y_train = smote.fit_resample(X_train_scaled, y_train)
            print(f"  - New training set shape after SMOTE: {X_train_scaled.shape}")

    print("[*] Data loading and preprocessing complete.")
    
    # Report class distributions
    print("\n--- Class Distributions ---")
    print("Train:", pd.Series(y_train).value_counts(normalize=True).to_dict())
    print("Val:", pd.Series(y_val).value_counts(normalize=True).to_dict())
    print("Test:", pd.Series(y_test).value_counts(normalize=True).to_dict())
    print("---------------------------\n")

    return (X_train_scaled, y_train), (X_val_scaled, y_val), (X_test_scaled, y_test), scaler, le


# --- Reinforcement Learning Components ---

class IDSEnvironment:
    """
    A simple Reinforcement Learning environment for the IDS task.
    Each data point is treated as an independent state.
    """
    def __init__(self, features, labels, reward_config):
        self.features = features
        self.labels = labels
        self.reward_config = reward_config
        self.current_index = 0
        self.num_samples = len(features)

    def reset(self):
        """Resets the environment to a new random state."""
        self.current_index = np.random.randint(0, self.num_samples)
        return self.features[self.current_index]

    def step(self, action):
        """
        Take an action and return the new state, reward, and done flag.
        In this i.i.d. setting, 'done' is always True.
        """
        true_label = self.labels[self.current_index]
        reward = self._get_reward(action, true_label)
        
        # Move to the next state for the next step in the episode (batch)
        self.current_index = (self.current_index + 1) % self.num_samples
        next_state = self.features[self.current_index]
        
        done = True  # Each state-action pair is a terminal episode
        return next_state, reward, done, {}

    def _get_reward(self, action, true_label):
        """Calculates the reward based on the action and true label."""
        is_attack = true_label != 0  # Assuming 0 is 'Benign'
        
        if action == true_label: # Correct classification
            return self.reward_config['correct_attack'] if is_attack else self.reward_config['correct_benign']
        else: # Incorrect classification
            if is_attack: # False Negative (attack -> benign)
                return self.reward_config['r_fn']
            else: # False Positive (benign -> attack)
                return self.reward_config['r_fp']

Experience = namedtuple('Experience', ('state', 'action', 'reward', 'next_state', 'done'))

class ReplayBuffer:
    """A simple ring buffer for storing experiences for DQN."""
    def __init__(self, capacity):
        self.buffer = deque(maxlen=capacity)

    def push(self, *args):
        """Saves a transition."""
        self.buffer.append(Experience(*args))

    def sample(self, batch_size):
        """Randomly sample a batch of experiences."""
        return random.sample(self.buffer, batch_size)

    def __len__(self):
        return len(self.buffer)

# --- Model Architecture ---

class MLP_QNetwork(nn.Module):
    """
    A Multi-Layer Perceptron for Q-value approximation in DQN.
    """
    def __init__(self, n_observations, n_actions, hidden_dims, dropout):
        super(MLP_QNetwork, self).__init__()
        
        layers = []
        input_dim = n_observations
        for h_dim in hidden_dims:
            layers.append(nn.Linear(input_dim, h_dim))
            layers.append(nn.BatchNorm1d(h_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            input_dim = h_dim
            
        layers.append(nn.Linear(input_dim, n_actions))
        
        self.network = nn.Sequential(*layers)

        # Initialize weights
        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.kaiming_normal_(module.weight, mode='fan_in', nonlinearity='relu')
            if module.bias is not None:
                nn.init.constant_(module.bias, 0)

    def forward(self, x):
        return self.network(x)

# --- DQN Agent ---

class DQN_Agent:
    """
    Double Deep Q-Network Agent.
    """
    def __init__(self, state_dim, action_dim, hidden_dims, dropout, lr, gamma, tau, epsilon_start, epsilon_end, epsilon_decay, device):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = device
        self.gamma = gamma
        self.tau = tau
        self.epsilon = epsilon_start
        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        
        self.policy_net = MLP_QNetwork(state_dim, action_dim, hidden_dims, dropout).to(device)
        self.target_net = MLP_QNetwork(state_dim, action_dim, hidden_dims, dropout).to(device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.AdamW(self.policy_net.parameters(), lr=lr)
        self.loss_fn = nn.SmoothL1Loss() # Huber Loss

    def select_action(self, state, train=True):
        """Selects an action using an epsilon-greedy policy."""
        if train and random.random() < self.epsilon:
            return torch.tensor([[random.randrange(self.action_dim)]], device=self.device, dtype=torch.long)
        else:
            with torch.no_grad():
                # state is expected to be a single sample, needs to be unsqueezed
                if state.dim() == 1:
                    state = state.unsqueeze(0)
                q_values = self.policy_net(state)
                return q_values.max(1)[1].view(1, 1)

    def decay_epsilon(self):
        """Decay epsilon value."""
        if self.epsilon > self.epsilon_end:
            self.epsilon *= self.epsilon_decay
        if self.epsilon < self.epsilon_end:
            self.epsilon = self.epsilon_end
            
    def update_target_net(self):
        """Soft update of the target network's weights."""
        target_net_state_dict = self.target_net.state_dict()
        policy_net_state_dict = self.policy_net.state_dict()
        for key in policy_net_state_dict:
            target_net_state_dict[key] = policy_net_state_dict[key] * self.tau + target_net_state_dict[key] * (1 - self.tau)
        self.target_net.load_state_dict(target_net_state_dict)

    def optimize_model(self, memory, batch_size, scaler):
        """
        Performs one step of optimization on the policy network.
        """
        if len(memory) < batch_size:
            return None

        experiences = memory.sample(batch_size)
        batch = Experience(*zip(*experiences))

        # Convert batch to tensors
        state_batch = torch.cat([s.unsqueeze(0) for s in batch.state]).to(self.device)
        action_batch = torch.cat(batch.action).to(self.device)
        reward_batch = torch.cat(batch.reward).to(self.device)
        next_state_batch = torch.cat([s.unsqueeze(0) for s in batch.next_state]).to(self.device)
        done_batch = torch.tensor(batch.done, device=self.device, dtype=torch.float32)

        # Compute Q(s_t, a)
        q_values = self.policy_net(state_batch).gather(1, action_batch)

        # Compute V(s_{t+1}) for all next states.
        # Use Double DQN: actions from policy_net, values from target_net
        with torch.no_grad():
            next_state_actions = self.policy_net(next_state_batch).max(1)[1].unsqueeze(1)
            next_state_q_values = self.target_net(next_state_batch).gather(1, next_state_actions)
        
        # Compute the expected Q values
        expected_q_values = (next_state_q_values * self.gamma * (1 - done_batch).unsqueeze(1)) + reward_batch.unsqueeze(1)

        # Compute Huber loss
        loss = self.loss_fn(q_values, expected_q_values)

        # Optimize the model
        self.optimizer.zero_grad()
        scaler.scale(loss).backward()
        # Clip gradients to prevent exploding gradients
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        scaler.step(self.optimizer)
        scaler.update()
        
        return loss.item()

# --- Evaluation ---

def evaluate(agent, dataloader, device, label_encoder):
    """Evaluate the agent's performance on a given dataset."""
    agent.policy_net.eval()
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for features, labels in dataloader:
            features = features.to(device)
            
            # Get Q-values and choose the action with the highest value
            q_values = agent.policy_net(features)
            preds = torch.argmax(q_values, dim=1)
            
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    agent.policy_net.train()

    accuracy = accuracy_score(all_labels, all_preds)
    precision, recall, f1, _ = precision_recall_fscore_support(
        all_labels, all_preds, average='weighted', zero_division=0
    )
    
    # For binary classification, also get attack-specific metrics
    attack_precision, attack_recall, attack_f1 = None, None, None
    if len(label_encoder.classes_) == 2:
        # Assuming 'Attack' is encoded as 1
        attack_class_index = 1 if 'Attack' in label_encoder.classes_ else 0
        if 'Attack' not in label_encoder.classes_[attack_class_index]:
             # Find the attack class if it's not at index 1
             for i, cls_name in enumerate(label_encoder.classes_):
                 if 'Attack' in cls_name:
                     attack_class_index = i
                     break
        
        p, r, f, _ = precision_recall_fscore_support(
            all_labels, all_preds, labels=[attack_class_index], average='binary', zero_division=0
        )
        attack_precision, attack_recall, attack_f1 = p, r, f

    metrics = {
        'accuracy': accuracy,
        'precision_weighted': precision,
        'recall_weighted': recall,
        'f1_weighted': f1,
        'attack_precision': attack_precision,
        'attack_recall': attack_recall,
        'attack_f1': attack_f1,
    }
    
    report = classification_report(all_labels, all_preds, target_names=label_encoder.classes_, zero_division=0, output_dict=True)
    
    return metrics, report, confusion_matrix(all_labels, all_preds)


# --- Main Training Loop ---

def main(args):
    """Main function to run the training and evaluation pipeline."""
    
    # --- Setup ---
    set_seed()
    
    # Create directories for logging and checkpoints
    run_name = f"IDS_RL_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    log_dir = Path(args.log_dir) / run_name
    ckpt_dir = Path(args.ckpt_dir) / run_name
    log_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    writer = SummaryWriter(log_dir)
    
    # Save config
    with open(log_dir / 'config.json', 'w') as f:
        json.dump(vars(args), f, indent=4)

    # Device setup
    if args.device == 'auto':
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    
    if device.type == 'cuda':
        print(f"[*] Using GPU: {torch.cuda.get_device_name(0)}")
        torch.backends.cudnn.benchmark = True
        # Allow TF32 for performance boost on Ampere GPUs
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    else:
        print("[*] Using CPU")

    # --- Data Loading ---
    (X_train, y_train), (X_val, y_val), (X_test, y_test), scaler, le = load_and_preprocess_data(
        args.data_dir, args.binary, args.use_smote
    )
    
    train_dataset = IntrusionDataset(X_train, y_train)
    val_dataset = IntrusionDataset(X_val, y_val)
    test_dataset = IntrusionDataset(X_test, y_test)
    
    # Handle class imbalance with weighted sampling if not using SMOTE
    sampler = None
    if args.use_class_weights and not args.use_smote:
        print("[*] Using WeightedRandomSampler to handle class imbalance.")
        class_counts = np.bincount(y_train)
        class_weights = 1. / class_counts
        sample_weights = np.array([class_weights[t] for t in y_train])
        sampler = WeightedRandomSampler(torch.from_numpy(sample_weights), len(sample_weights))

    train_loader = DataLoader(
        train_dataset, 
        batch_size=args.batch_size, 
        sampler=sampler,
        shuffle=sampler is None, # Shuffle only if not using a sampler
        num_workers=4 if device.type == 'cuda' else 0, 
        pin_memory=True if device.type == 'cuda' else False,
        persistent_workers=True if device.type == 'cuda' and sampler is None else False
    )
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size * 2, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size * 2, shuffle=False)

    # --- RL and Model Initialization ---
    n_observations = X_train.shape[1]
    n_actions = len(le.classes_)
    
    # A3C is not implemented in this version as it adds significant complexity.
    # The focus is on a robust DQN implementation as requested.
    if args.algo == 'a3c':
        print("Warning: A3C algorithm is not implemented in this script. Falling back to DQN.")
        args.algo = 'dqn'
        
    agent = DQN_Agent(
        state_dim=n_observations,
        action_dim=n_actions,
        hidden_dims=args.hidden_dims,
        dropout=args.dropout,
        lr=args.lr,
        gamma=0.99, # Discount factor
        tau=0.005, # Soft update rate
        epsilon_start=1.0,
        epsilon_end=0.05,
        epsilon_decay=0.995,
        device=device
    )
    
    # Compile model if requested and possible
    if args.compile and hasattr(torch, 'compile'):
        print("[*] Compiling the model with torch.compile()...")
        try:
            agent.policy_net = torch.compile(agent.policy_net)
            agent.target_net = torch.compile(agent.target_net)
            print("  - Model compiled successfully.")
        except Exception as e:
            print(f"  - Warning: torch.compile failed: {e}. Continuing without compilation.")

    memory = ReplayBuffer(10000)
    
    reward_config = {
        'correct_benign': 1,
        'correct_attack': 2,
        'r_fp': args.r_fp,
        'r_fn': args.r_fn
    }
    
    # Use a simplified env that just provides rewards for the current batch
    env = IDSEnvironment(X_train, y_train, reward_config)
    
    scaler_amp = torch.cuda.amp.GradScaler(enabled=(args.amp and device.type == 'cuda'))

    start_epoch = 0
    best_val_f1 = 0.0

    # --- Resume from Checkpoint ---
    if args.resume:
        if Path(args.resume).is_file():
            print(f"[*] Resuming training from checkpoint: {args.resume}")
            checkpoint = torch.load(args.resume, map_location=device)
            agent.policy_net.load_state_dict(checkpoint['model_state_dict'])
            agent.target_net.load_state_dict(checkpoint['model_state_dict']) # Sync target net
            agent.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            start_epoch = checkpoint['epoch'] + 1
            best_val_f1 = checkpoint.get('best_val_f1', 0.0)
            # The scaler and label encoder should be re-loaded from the new data run
            # to ensure consistency, but we could load them if they were saved.
            print(f"  - Resuming from epoch {start_epoch}, best F1 so far: {best_val_f1:.4f}")
        else:
            print(f"Warning: Checkpoint file not found at {args.resume}. Starting from scratch.")

    # --- Training Loop ---
    print(f"\n[*] Starting training for {args.epochs} epochs...")
    total_steps = 0
    for epoch in range(start_epoch, args.epochs):
        epoch_start_time = time.time()
        agent.policy_net.train()
        total_loss = 0
        total_reward = 0
        
        for i, (features, labels) in enumerate(train_loader):
            features = features.to(device)
            labels = labels.to(device)
            
            # Interact with environment and store in replay buffer
            for j in range(features.size(0)):
                state = features[j]
                true_label = labels[j].item()
                
                action = agent.select_action(state, train=True)
                
                # In our setup, next_state is just the next item in the dataset
                # This is a simplification for i.i.d. data
                next_idx = (i * args.batch_size + j + 1) % len(train_dataset)
                next_state, _ = train_dataset[next_idx]
                next_state = next_state.to(device)

                reward = env._get_reward(action.item(), true_label)
                total_reward += reward
                reward_tensor = torch.tensor([reward], device=device, dtype=torch.float32)
                
                done = True # Each step is an episode
                
                memory.push(state, action, reward_tensor, next_state, done)

            # Optimize model
            with torch.cuda.amp.autocast(enabled=(args.amp and device.type == 'cuda')):
                loss = agent.optimize_model(memory, args.batch_size, scaler_amp)
            
            if loss is not None:
                total_loss += loss
            
            total_steps += features.size(0)
            
        # Decay epsilon and update target network
        agent.decay_epsilon()
        agent.update_target_net()

        avg_loss = total_loss / len(train_loader) if len(train_loader) > 0 else 0
        avg_reward = total_reward / len(train_dataset) if len(train_dataset) > 0 else 0
        
        # --- Validation ---
        val_metrics, _, _ = evaluate(agent, val_loader, device, le)
        val_f1 = val_metrics['attack_f1'] if args.binary and val_metrics['attack_f1'] is not None else val_metrics['f1_weighted']
        
        epoch_duration = time.time() - epoch_start_time
        
        print(
            f"Epoch {epoch+1}/{args.epochs} | Time: {epoch_duration:.2f}s | "
            f"Loss: {avg_loss:.4f} | Avg Reward: {avg_reward:.4f} | "
            f"Val F1: {val_f1:.4f} | Epsilon: {agent.epsilon:.4f}"
        )

        # --- Logging ---
        writer.add_scalar('Loss/train', avg_loss, epoch)
        writer.add_scalar('Reward/train', avg_reward, epoch)
        writer.add_scalar('Params/epsilon', agent.epsilon, epoch)
        writer.add_scalar('Params/learning_rate', agent.optimizer.param_groups[0]['lr'], epoch)
        
        for metric_name, value in val_metrics.items():
            if value is not None:
                writer.add_scalar(f'Val/{metric_name}', value, epoch)

        # --- Checkpointing ---
        is_best = val_f1 > best_val_f1
        if is_best:
            best_val_f1 = val_f1
            checkpoint_path = ckpt_dir / 'best_model.pth'
            print(f"  - New best model found! Saving to {checkpoint_path}")
            torch.save({
                'epoch': epoch,
                'model_state_dict': agent.policy_net.state_dict(),
                'optimizer_state_dict': agent.optimizer.state_dict(),
                'best_val_f1': best_val_f1,
                'config': vars(args),
                # Note: Saving scaler and encoder is crucial for inference
                'scaler': scaler,
                'label_encoder': le
            }, checkpoint_path)

    writer.close()
    print("\n[*] Training finished.")

    # --- Final Evaluation on Test Set ---
    print("\n[*] Evaluating on the test set with the best model...")
    best_model_path = ckpt_dir / 'best_model.pth'
    if best_model_path.exists():
        checkpoint = torch.load(best_model_path, map_location=device)
        agent.policy_net.load_state_dict(checkpoint['model_state_dict'])
        
        test_metrics, test_report, test_cm = evaluate(agent, test_loader, device, le)
        
        print("\n--- Test Set Performance ---")
        print(f"  Accuracy: {test_metrics['accuracy']:.4f}")
        print(f"  Weighted F1-Score: {test_metrics['f1_weighted']:.4f}")
        if args.binary:
            print(f"  Attack Recall: {test_metrics['attack_recall']:.4f}")
            print(f"  Attack Precision: {test_metrics['attack_precision']:.4f}")
            print(f"  Attack F1-Score: {test_metrics['attack_f1']:.4f}")
        
        print("\nClassification Report:")
        print(pd.DataFrame(test_report).transpose())

        print("\nConfusion Matrix:")
        print(test_cm)
        
        # Save final metrics
        final_metrics = {
            'test_metrics': test_metrics,
            'classification_report': test_report,
            'confusion_matrix': test_cm.tolist()
        }
        with open(log_dir / 'final_metrics.json', 'w') as f:
            json.dump(final_metrics, f, indent=4)
        print(f"\n[*] Final metrics saved to {log_dir / 'final_metrics.json'}")

    else:
        print("Warning: No best model checkpoint found. Skipping final evaluation.")

    print(f"\n[*] All artifacts saved in: {log_dir.parent.resolve()}")
    print("To view logs, run the following command in your terminal:")
    print(f"tensorboard --logdir=\"{log_dir.parent.resolve()}\"")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Adaptive Intrusion Detection System using Reinforcement Learning.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # --- Data and Path Arguments ---
    parser.add_argument('--data-dir', type=str, default=r'C:\AIML\Projects\adaptive-ids\data',
                        help='Path to the directory containing CSE-CIC-IDS2018 CSV files.')
    parser.add_argument('--log-dir', type=str, default='/runs', help='Directory for TensorBoard logs.')
    parser.add_argument('--ckpt-dir', type=str, default='/checkpoints', help='Directory for model checkpoints.')
    parser.add_argument('--resume', type=str, default=None, help='Path to checkpoint to resume training from.')

    # --- Model and Training Arguments ---
    parser.add_argument('--algo', type=str, default='dqn', choices=['dqn', 'a3c'],
                        help='Reinforcement learning algorithm to use. (Note: a3c is not implemented)')
    parser.add_argument('--binary', action='store_true', help='Perform binary classification (Benign vs Attack).')
    parser.add_argument('--epochs', type=int, default=20, help='Number of training epochs.')
    parser.add_argument('--batch-size', type=int, default=2048, help='Batch size for training.')
    parser.add_argument('--lr', type=float, default=1e-4, help='Learning rate for the optimizer.')
    parser.add_argument('--hidden-dims', nargs='+', type=int, default=[256, 128], help='Hidden layer dimensions for the MLP.')
    parser.add_argument('--dropout', type=float, default=0.3, help='Dropout rate in the MLP.')

    # --- Reward Shaping Arguments ---
    parser.add_argument('--r_fp', type=float, default=-1.0, help='Reward for a false positive.')
    parser.add_argument('--r_fn', type=float, default=-5.0, help='Reward for a false negative.')

    # --- Class Imbalance Arguments ---
    parser.add_argument('--use-smote', action='store_true', help='Use SMOTE for oversampling the minority class.')
    parser.add_argument('--use-class-weights', action='store_true', help='Use weighted sampling based on class frequency.')
    
    # --- Performance and System Arguments ---
    parser.add_argument('--device', type=str, default='auto', choices=['auto', 'cuda', 'cpu'],
                        help='Device to use for training.')
    parser.add_argument('--no-compile', dest='compile', action='store_false',
                        help='Disable torch.compile().')
    parser.add_argument('--no-amp', dest='amp', action='store_false',
                        help='Disable Automatic Mixed Precision (AMP).')

    args = parser.parse_args()
    
    # Print configuration
    print("\n--- Configuration ---")
    for key, value in vars(args).items():
        print(f"  {key}: {value}")
    print("---------------------\n")

    if args.use_smote and args.use_class_weights:
        print("Warning: Both --use-smote and --use-class-weights are specified. SMOTE will be used, and weighted sampling will be disabled.")
        args.use_class_weights = False

    try:
        main(args)
    except Exception as e:
        print(f"\n[!] An error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
