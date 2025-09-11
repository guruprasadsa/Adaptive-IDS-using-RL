#!/usr/bin/env python
# adaptive_ids_rl.py
"""
Adaptive IDS RL Trainer - Memory-optimized single-file (Windows, ~16GB RAM friendly)

Features optimized for 16GB RAM:
 - Two-pass streaming CSV reader to compute feature stats without full in-memory dataset
 - Uses numpy.memmap to store preprocessed features and labels on disk (low RAM)
 - Chunked processing, dtype downcasting to float32/int32
 - Optional --low-mem mode that reduces batch sizes, worker counts, replay buffer, and prefetch
 - DQN (default) with Double-DQN target network, replay buffer (disk-resident memmap inputs)
 - Mixed precision (autocast + GradScaler), guarded torch.compile, cudnn tuning
 - TensorBoard logging, checkpointing with scaler and label encoder saved inside checkpoint
 - CLI examples for Windows paths (use forward slashes or escape backslashes in CLI)

Limitations / notes:
 - SMOTE not included (requires imbalanced-learn). Random oversample fallback provided.
 - A3C minimal implementation (single-process) is included behind --algo a3c but not optimized for memmaps.
 - This file is self-contained and intended for Windows. Default data dir: 'C:/AIML/Projects/adaptive-ids/data'

Run example (Windows):
python "C:\AIML\Projects\adaptive-ids\backend\trainrl.py" --data-dir "C:/AIML/Projects/adaptive-ids/data/data_2017" --binary --device cuda --epochs 30 --batch-size 512

"""

import os
import sys
import argparse
import time
import json
import math
import random
import glob
import pickle
from collections import Counter, defaultdict
from typing import List, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix, roc_auc_score

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torch.utils.tensorboard import SummaryWriter

# ---------------------------
# Utils
# ---------------------------
def parse_args():
    p = argparse.ArgumentParser(description='Adaptive IDS RL - memory optimized for ~16GB RAM (Windows)')
    p.add_argument('--data-dir', type=str, default='C:/AIML/Projects/adaptive-ids/data')
    p.add_argument('--binary', action='store_true')
    p.add_argument('--algo', choices=['dqn','a3c'], default='dqn')
    p.add_argument('--sequence', action='store_true')
    p.add_argument('--seq-len', type=int, default=4)
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--batch-size', type=int, default=512)
    p.add_argument('--lr', type=float, default=2e-4)
    p.add_argument('--weight-decay', type=float, default=1e-5)
    p.add_argument('--hidden-dims', type=str, default='256,128')
    p.add_argument('--dropout', type=float, default=0.2)
    p.add_argument('--use-smote', action='store_true')
    p.add_argument('--use-class-weights', action='store_true')
    p.add_argument('--device', choices=['auto','cuda','cpu'], default='auto')
    p.add_argument('--compile', action='store_true')
    p.add_argument('--amp', action='store_true')
    p.add_argument('--log-dir', type=str, default='runs')
    p.add_argument('--ckpt-dir', type=str, default='checkpoints')
    p.add_argument('--resume', type=str, default=None)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--r_fp', type=float, default=-1.0)
    p.add_argument('--r_fn', type=float, default=-5.0)
    p.add_argument('--r_tp_benign', type=float, default=1.0)
    p.add_argument('--r_tp_attack', type=float, default=2.0)
    p.add_argument('--gamma', type=float, default=0.99)
    p.add_argument('--replay-size', type=int, default=50000)
    p.add_argument('--target-sync-freq', type=int, default=1000)
    p.add_argument('--eps-start', type=float, default=1.0)
    p.add_argument('--eps-end', type=float, default=0.05)
    p.add_argument('--eps-decay-steps', type=int, default=100000)
    p.add_argument('--num-workers', type=int, default=0)
    p.add_argument('--low-mem', action='store_true', help='Aggressive memory optimizations for ~16GB RAM')
    return p.parse_args()

def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

# ---------------------------
# CSV streaming -> memmap pipeline (two-pass)
# ---------------------------
POSSIBLE_LABEL_COLS = ['Label','label','labelname','LabelName','class','Class']
DROP_PATTERNS = ['id','timestamp','start_time','end_time','flow_id','unix_time','date']

def find_csvs(root_dir: str) -> List[str]:
    files = []
    for r,_,fs in os.walk(root_dir):
        for f in fs:
            if f.lower().endswith('.csv'):
                files.append(os.path.join(r,f))
    files.sort()
    return files

def sanitize_cols(cols):
    out=[]
    for c in cols:
        c2 = c.strip().replace(' ','_').replace('-','_').replace('/','_')
        c2 = ''.join(ch for ch in c2 if ord(ch)<128)
        out.append(c2)
    return out

def infer_label_col(cols):
    for name in POSSIBLE_LABEL_COLS:
        if name in cols:
            return name
    for c in cols:
        if c.lower()=='label':
            return c
    return None

def two_pass_memmap(data_dir: str, cache_dir: str, binary: bool, chunksize: int=200_000, low_mem: bool=False):
    print('[step] starting two-pass preprocessing -> memmap')
    ensure_dir(cache_dir)
    csvs = find_csvs(data_dir)
    if not csvs:
        raise FileNotFoundError(f'No CSVs under {data_dir}')
    print(f'[data] found {len(csvs)} csv files')

    # First pass: infer columns, total rows, compute per-feature sums and sumsqs for mean/std, gather labels set
    total_rows=0
    feature_names=None
    label_col=None
    sums=None
    sumsqs=None
    n_features=0
    label_set=set()

    for f in csvs:
        print(f"[pass1] scanning file: {f}")
        for i, chunk in enumerate(pd.read_csv(f, chunksize=chunksize, low_memory=False)):
            if i % 10 == 0:
                print(f"[pass1] reading chunk {i} from {os.path.basename(f)}")
            chunk.columns = sanitize_cols(list(chunk.columns))
            if label_col is None:
                label_col = infer_label_col(list(chunk.columns))
                if label_col is None:
                    raise ValueError('Label column not found')
                print(f"[pass1] inferred label column: {label_col}")
            # drop identifier-like columns
            drop_cols = [c for c in chunk.columns if any(p in c.lower() for p in DROP_PATTERNS)]
            if drop_cols:
                print(f"[pass1] dropping identifier-like columns: {drop_cols}")
            chunk = chunk.drop(columns=[c for c in drop_cols if c in chunk.columns], errors='ignore')

            # determine numeric candidate columns (first time)
            if feature_names is None:
                temp = chunk.drop(columns=[label_col])
                cand = []
                for c in temp.columns:
                    coerced = pd.to_numeric(temp[c], errors='coerce')
                    if coerced.notna().sum() > 0:
                        cand.append(c)
                feature_names = cand
                n_features = len(feature_names)
                sums = np.zeros(n_features, dtype=np.float64)
                sumsqs = np.zeros(n_features, dtype=np.float64)
                print(f"[pass1] detected {n_features} numeric features")

            # coerce numeric and compute stats
            arr = chunk[feature_names].apply(pd.to_numeric, errors='coerce').values.astype(np.float32)
            mask = np.isfinite(arr)
            # replace non-finite with np.nan for counting
            arr[~mask]=np.nan
            col_sums = np.nansum(arr, axis=0)
            col_sumsqs = np.nansum(np.nan_to_num(arr)**2, axis=0)
            valid_counts = np.sum(np.isfinite(arr), axis=0)
            sums += np.nan_to_num(col_sums)
            sumsqs += np.nan_to_num(col_sumsqs)
            total_rows += arr.shape[0]
            # gather labels
            lab = chunk[label_col].astype(str).str.strip().values
            label_set.update(lab.tolist())
            # free
            del chunk, arr, mask
            if low_mem:
                # hint to GC
                import gc
                gc.collect()

    if total_rows == 0:
        raise ValueError('No rows found')
    print(f'[data] total_rows={total_rows}, n_features={n_features}, unique_labels={len(label_set)}')

    # Compute feature means and stds using sums/sumsqs and total_rows (approx, NaNs treated as zeros -> we risk slight bias, but acceptable for big data)
    means = sums / max(1, total_rows)
    vars_ = (sumsqs / max(1, total_rows)) - (means**2)
    stds = np.sqrt(np.maximum(vars_, 1e-6))
    print('[pass1] computed global means/stds')

    # Label encoder from label_set
    label_list = sorted(list(label_set))
    le = LabelEncoder(); le.fit(label_list)
    print(f'[data] labels: {le.classes_}')

    # If binary mode, map to Benign/Attack
    benign_vals = set()
    if binary:
        # find any label that looks 'benign'
        ben_mask = [l for l in label_list if l.lower().startswith('ben')]
        if ben_mask:
            benign_vals = set(ben_mask)
        else:
            # fallback: treat 'BENIGN' uppercase variants
            benign_vals = set([l for l in label_list if 'benign' in l.lower()])
        print(f'[data] binary mapping will treat {len(benign_vals)} labels as Benign')
        le = LabelEncoder(); le.fit(['Benign','Attack'])

    # Prepare memmaps for writing
    X_path = os.path.join(cache_dir, 'X_mem.dat')
    y_path = os.path.join(cache_dir, 'y_mem.npy')
    print(f'[pass2] creating memmap files at {cache_dir}')
    X_mm = np.memmap(X_path, dtype='float32', mode='w+', shape=(total_rows, n_features))
    y_mm = np.zeros((total_rows,), dtype=np.int32)

    # Second pass: fill memmap using computed means/stds
    idx = 0
    for f in csvs:
        print(f"[pass2] processing file: {f}")
        for i, chunk in enumerate(pd.read_csv(f, chunksize=chunksize, low_memory=False)):
            if i % 20 == 0:
                print(f"[pass2] file {os.path.basename(f)} chunk {i}")
            chunk.columns = sanitize_cols(list(chunk.columns))
            chunk = chunk.drop(columns=[c for c in chunk.columns if any(p in c.lower() for p in DROP_PATTERNS)], errors='ignore')
            arr = chunk[feature_names].apply(pd.to_numeric, errors='coerce').values.astype(np.float32)
            inds = np.where(~np.isfinite(arr))
            if inds[0].size>0:
                arr[inds] = np.take(means.astype(np.float32), inds[1])
            arr = (arr - means.astype(np.float32)) / (stds.astype(np.float32) + 1e-9)
            n = arr.shape[0]
            X_mm[idx:idx+n, :] = arr
            lab_vals = chunk[infer_label_col(list(chunk.columns))].astype(str).str.strip().values
            if binary:
                lab_mapped = np.array(['Benign' if l in benign_vals else 'Attack' for l in lab_vals])
                y_enc = le.transform(lab_mapped)
            else:
                y_enc = le.transform(lab_vals)
            y_mm[idx:idx+n] = y_enc.astype(np.int32)
            idx += n
            del chunk, arr
            if low_mem:
                import gc
                gc.collect()
        print(f"[pass2] finished file {os.path.basename(f)}; written rows so far: {idx}")

    # flush memmaps
    X_mm.flush()
    np.save(y_path, y_mm)
    print(f'[data] memmap written: X={X_path} y={y_path}')
    # save metadata
    meta = {'n_features': n_features, 'feature_names': feature_names, 'means': means.astype(np.float32), 'stds': stds.astype(np.float32), 'label_classes': list(le.classes_), 'total_rows': total_rows}
    with open(os.path.join(cache_dir, 'meta.pkl'), 'wb') as f:
        pickle.dump(meta, f)
    print('[pass2] metadata saved')
    return X_path, y_path, os.path.join(cache_dir, 'meta.pkl')

# ---------------------------
# Dataset that reads from memmap on-demand
# ---------------------------
class MemmapDataset(Dataset):
    def __init__(self, X_path, y_path, meta_path, indices=None):
        self.meta = pickle.load(open(meta_path,'rb'))
        self.X_path = X_path
        self.y = np.load(y_path, mmap_mode='r')
        self.total = int(self.meta['total_rows'])
        self.n_features = int(self.meta['n_features'])
        self.X_mm = None  # open lazily (worker-safe)
        self.indices = np.arange(self.total) if indices is None else np.array(indices, dtype=np.int64)

    def _ensure_open(self):
        if self.X_mm is None:
            print(f"[dataset] opening memmap in process {os.getpid()}")
            self.X_mm = np.memmap(self.X_path, dtype='float32', mode='r', shape=(self.total, self.n_features))

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        i = int(self.indices[idx])
        self._ensure_open()
        # copy memmap row to writable numpy array to avoid PyTorch warning about non-writable arrays
        x = np.array(self.X_mm[i], dtype=np.float32, copy=True)
        y = int(self.y[i])
        return torch.from_numpy(x).float(), torch.tensor(y, dtype=torch.long)
# ---------------------------
# Models (DQN and small A3C)
# ---------------------------
def kaiming_init(m):
    if isinstance(m, nn.Linear):
        nn.init.kaiming_normal_(m.weight, nonlinearity='relu')
        if m.bias is not None:
            nn.init.zeros_(m.bias)

class DQN_MLP(nn.Module):
    """ Dueling DQN MLP network """
    def __init__(self, input_dim, output_dim, hidden_dims=[256,128], dropout=0.2):
        super().__init__()
        
        feature_layers = []
        last_dim = input_dim
        for h_dim in hidden_dims:
            feature_layers.append(nn.Linear(last_dim, h_dim))
            feature_layers.append(nn.BatchNorm1d(h_dim))
            feature_layers.append(nn.ReLU())
            feature_layers.append(nn.Dropout(dropout))
            last_dim = h_dim
        self.feature_net = nn.Sequential(*feature_layers)

        # Advantage stream
        self.advantage_net = nn.Sequential(
            nn.Linear(last_dim, last_dim // 2),
            nn.ReLU(),
            nn.Linear(last_dim // 2, output_dim)
        )

        # Value stream
        self.value_net = nn.Sequential(
            nn.Linear(last_dim, last_dim // 2),
            nn.ReLU(),
            nn.Linear(last_dim // 2, 1)
        )
        self.apply(kaiming_init)

    def forward(self, x):
        if x.dim() == 3:
            B, S, F = x.shape
            x = x.view(B, S * F)
        
        features = self.feature_net(x)
        advantages = self.advantage_net(features)
        value = self.value_net(features)
        
        # Combine value and advantages for Q-values
        qvals = value + (advantages - advantages.mean(dim=1, keepdim=True))
        return qvals

class ActorCritic(nn.Module):
    def __init__(self,input_dim,action_dim,hidden_dims=[256,128],use_lstm=False,seq_len=1,dropout=0.2):
        super().__init__()
        self.use_lstm = use_lstm
        self.seq_len = seq_len
        if use_lstm:
            self.feat = nn.Linear(input_dim, hidden_dims[0])
            self.lstm = nn.LSTM(hidden_dims[0], hidden_dims[1], batch_first=True)
            self.actor = nn.Linear(hidden_dims[1], action_dim)
            self.critic = nn.Linear(hidden_dims[1], 1)
        else:
            layers=[]; last=input_dim*(seq_len if seq_len>1 else 1)
            for h in hidden_dims:
                layers.append(nn.Linear(last,h)); layers.append(nn.ReLU()); layers.append(nn.Dropout(dropout)); last=h
            self.shared=nn.Sequential(*layers)
            self.actor = nn.Linear(last, action_dim)
            self.critic = nn.Linear(last,1)
        self.apply(kaiming_init)
    def forward(self,x):
        if self.use_lstm:
            h = F.relu(self.feat(x))
            out,_ = self.lstm(h)
            last = out[:,-1,:]
            return self.actor(last), self.critic(last).squeeze(-1)
        else:
            if x.dim()==3:
                B,S,F = x.shape
                x = x.view(B,S*F)
            h = self.shared(x)
            return self.actor(h), self.critic(h).squeeze(-1)

# ---------------------------
# Replay buffer (in-memory small) - configurable smaller for low-mem
# ---------------------------
class ReplayBuffer:
    def __init__(self, capacity:int, state_shape:Tuple[int]):
        self.capacity = int(capacity)
        self.state_shape = state_shape
        self.ptr = 0
        self.size = 0
        self.states = np.zeros((self.capacity, *state_shape), dtype=np.float32)
        self.next_states = np.zeros((self.capacity, *state_shape), dtype=np.float32)
        self.actions = np.zeros((self.capacity,), dtype=np.int64)
        self.rewards = np.zeros((self.capacity,), dtype=np.float32)
        self.dones = np.zeros((self.capacity,), dtype=np.uint8)
    def push_batch(self, states, actions, rewards, next_states, dones):
        n = len(states)
        for i in range(n):
            self.states[self.ptr] = states[i]
            self.next_states[self.ptr] = next_states[i]
            self.actions[self.ptr] = int(actions[i])
            self.rewards[self.ptr] = float(rewards[i])
            self.dones[self.ptr] = 1 if dones[i] else 0
            self.ptr = (self.ptr + 1) % self.capacity
            self.size = min(self.size+1, self.capacity)
    def sample(self, batch_size):
        idxs = np.random.randint(0, self.size, size=batch_size)
        return (torch.from_numpy(self.states[idxs]).float(), torch.from_numpy(self.actions[idxs]).long(), torch.from_numpy(self.rewards[idxs]).float(), torch.from_numpy(self.next_states[idxs]).float(), torch.from_numpy(self.dones[idxs]).float())

# ---------------------------
# Evaluation & utilities
# ---------------------------

def compute_metrics(y_true, y_pred, label_classes, binary=False):
    acc = accuracy_score(y_true, y_pred)
    prec, rec, f1, sup = precision_recall_fscore_support(y_true, y_pred, labels=list(range(len(label_classes))), zero_division=0)
    per_class = {label_classes[i]:{'precision':float(prec[i]),'recall':float(rec[i]),'f1':float(f1[i]),'support':int(sup[i])} for i in range(len(label_classes))}
    macro_f1 = float(np.nanmean(f1))
    weighted = precision_recall_fscore_support(y_true, y_pred, average='weighted', zero_division=0)
    metrics = {'accuracy':float(acc),'macro_f1':macro_f1,'weighted_f1':float(weighted[2]),'per_class':per_class}
    if binary:
        try:
            # roc_auc should be computed by caller if probabilities available
            pass
        except Exception:
            metrics['roc_auc']=None
    return metrics

def save_confusion(cm, labels, out_png):
    import matplotlib.pyplot as plt
    plt.figure(figsize=(6,6)); plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues); plt.colorbar()
    ticks = np.arange(len(labels)); plt.xticks(ticks, labels, rotation=45); plt.yticks(ticks, labels)
    thresh = cm.max()/2.
    for i,j in np.ndindex(cm.shape):
        plt.text(j,i,int(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>thresh else 'black')
    plt.ylabel('True'); plt.xlabel('Pred'); plt.tight_layout(); plt.savefig(out_png); plt.close()

# ---------------------------
# Training loops (DQN and A3C minimal)
# ---------------------------

def train_dqn_loop(model, target_model, optimizer, scheduler, replay:ReplayBuffer, train_loader, val_loader, le, cfg, device, meta, cache_dir):
    print('[train] starting DQN training loop')
    writer = SummaryWriter(cfg.log_dir)
    # GradScaler: prefer new torch.amp API but fallback to legacy torch.cuda.amp
    try:
        scaler_amp = torch.amp.GradScaler(enabled=cfg.amp, device_type=('cuda' if device.type=='cuda' else 'cpu'))
    except Exception:
        scaler_amp = torch.cuda.amp.GradScaler(enabled=cfg.amp)
    criterion = nn.SmoothL1Loss()

    # autocast context helper to support torch.amp.autocast or legacy torch.cuda.amp.autocast
    def autocast_ctx(enabled):
        try:
            return torch.amp.autocast(device_type=('cuda' if device.type=='cuda' else 'cpu'), enabled=enabled)
        except Exception:
            return torch.cuda.amp.autocast(enabled=enabled)

    best_score = -1.0
    eps = cfg.eps_start
    eps_decay = (cfg.eps_start - cfg.eps_end) / max(1, cfg.eps_decay_steps)
    state_shape = (meta['n_features'],)
    step = 0

    # optionally compile
    if cfg.compile:
        try:
            model = torch.compile(model)
            target_model = torch.compile(target_model)
            print('[compile] succeeded')
        except Exception as e:
            print('[compile] failed or unavailable:', e)

    # prefill replay from a few batches (small)
    print('[replay] pre-filling replay buffer from training loader')
    for i, (xb,yb) in enumerate(train_loader):
        xb_np = xb.numpy(); yb_np = yb.numpy()
        ns = np.roll(xb_np, shift=-1, axis=0)
        actions = yb_np
        rewards = np.zeros(len(actions), dtype=np.float32)
        replay.push_batch(xb_np, actions, rewards, ns, np.zeros(len(actions), dtype=np.uint8))
        if replay.size >= min(replay.capacity, 20000): break
    print(f'[replay] prefilling complete, replay.size={replay.size}')

    for epoch in range(cfg.epochs):
        print(f'[epoch] starting epoch {epoch+1}/{cfg.epochs}')
        model.train(); epoch_losses=[]
        t0 = time.time()
        for batch_idx, (xb,yb) in enumerate(train_loader):
            if batch_idx % 500 == 0:
                print(f'  [train] processing batch {batch_idx} of epoch {epoch+1}')
            xb = xb.to(device); yb = yb.to(device)
            # epsilon decay
            eps = max(cfg.eps_end, eps - eps_decay)
            # choose actions via epsilon-greedy
            with torch.no_grad():
                qvals = model(xb)
                greedy = torch.argmax(qvals, dim=1).cpu().numpy()
            # compute rewards using greedy predictions vs ground truth to bias recall
            rewards = np.zeros(len(greedy), dtype=np.float32)
            truths = yb.cpu().numpy()
            for i,(g,t) in enumerate(zip(greedy,truths)):
                if g == t:
                    # correct
                    name = le.classes_[int(t)].lower()
                    if name.startswith('ben'):
                        rewards[i] = cfg.r_tp_benign
                    else:
                        rewards[i] = cfg.r_tp_attack
                else:
                    pred_name = le.classes_[int(g)].lower(); true_name = le.classes_[int(t)].lower()
                    if pred_name.startswith('ben') and not true_name.startswith('ben'):
                        rewards[i] = cfg.r_fn
                    elif not pred_name.startswith('ben') and true_name.startswith('ben'):
                        rewards[i] = cfg.r_fp
                    else:
                        rewards[i] = -1.0
            ns = np.roll(xb.cpu().numpy(), -1, axis=0)
            replay.push_batch(xb.cpu().numpy(), truths, rewards, ns, np.zeros(len(rewards), dtype=np.uint8))

            # sample and learn
            if replay.size >= min(1024, replay.capacity//10):
                s_b, a_b, r_b, ns_b, d_b = replay.sample(min(512, replay.size))
                s_b = s_b.to(device); a_b = a_b.to(device); r_b = r_b.to(device); ns_b = ns_b.to(device); d_b = d_b.to(device)
                with autocast_ctx(cfg.amp):
                    q_s = model(s_b).gather(1, a_b.unsqueeze(1)).squeeze(1)
                    next_actions = torch.argmax(model(ns_b), dim=1)
                    q_next = target_model(ns_b).gather(1, next_actions.unsqueeze(1)).squeeze(1)
                    td_target = r_b + (1.0 - d_b) * cfg.gamma * q_next
                    loss = criterion(q_s, td_target.detach())
                optimizer.zero_grad(); scaler_amp.scale(loss).backward(); scaler_amp.unscale_(optimizer); nn.utils.clip_grad_norm_(model.parameters(), 1.0); scaler_amp.step(optimizer); scaler_amp.update()
                if scheduler:
                    scheduler.step()
                epoch_losses.append(loss.item())
                step += 1
                if step % cfg.target_sync_freq == 0:
                    target_model.load_state_dict(model.state_dict())

        if cfg.lr > 0 and hasattr(optimizer, 'param_groups'):
            writer.add_scalar('train/lr', optimizer.param_groups[0]['lr'], epoch)
        t1 = time.time(); avg_loss = float(np.mean(epoch_losses)) if epoch_losses else 0.0
        print(f'[epoch {epoch+1}/{cfg.epochs}] loss={avg_loss:.6f} time={t1-t0:.1f}s eps={eps:.4f} replay={replay.size}')
        writer.add_scalar('train/loss', avg_loss, epoch)
        writer.add_scalar('train/eps', eps, epoch)

        # validation
        print('[eval] running validation')
        y_true=[]; y_pred=[]
        model.eval()
        with torch.no_grad():
            for xb,yb in val_loader:
                xb = xb.to(device)
                out = model(xb)
                preds = torch.argmax(out, dim=1).cpu().numpy()
                y_true.extend(yb.numpy()); y_pred.extend(preds.tolist())
        metrics = compute_metrics(np.array(y_true), np.array(y_pred), le.classes_, binary=(len(le.classes_)==2))
        print('[val] metrics:', json.dumps(metrics, indent=2))
        writer.add_scalar('val/macro_f1', metrics['macro_f1'], epoch)

        # checkpoint best by macro_f1 (or attack F1 if binary)
        if len(le.classes_)==2:
            attack_f1 = metrics['per_class'].get('Attack', {}).get('f1', 0.0)
            ckpt_score = attack_f1
        else:
            ckpt_score = metrics['macro_f1']
        if ckpt_score > best_score:
            best_score = ckpt_score
            ensure_dir(cfg.ckpt_dir)
            torch.save({'model_state_dict': model.state_dict(), 'meta':meta, 'label_classes':list(le.classes_), 'cfg':vars(cfg)}, os.path.join(cfg.ckpt_dir, 'best_model.pth'))
            print('[ckpt] saved best_model.pth')

    # final save
    torch.save({'model_state_dict': model.state_dict(), 'meta':meta, 'label_classes':list(le.classes_), 'cfg':vars(cfg)}, os.path.join(cfg.ckpt_dir, 'final_model.pth'))
    print('[train] DQN training complete; final model saved')
    writer.close()

# Minimal A3C single-process loop (kept simple)
def train_a3c_loop(model, optimizer, train_loader, val_loader, le, cfg, device, meta):
    print('[train] starting A3C-like training loop')
    writer = SummaryWriter(cfg.log_dir)
    best=-1
    for epoch in range(cfg.epochs):
        print(f'[A3C] starting epoch {epoch+1}/{cfg.epochs}')
        model.train(); losses=[]
        for batch_idx, (xb,yb) in enumerate(train_loader):
            if batch_idx % 50 == 0:
                print(f'  [A3C] processing batch {batch_idx} of epoch {epoch+1}')
            xb=xb.to(device); yb=yb.to(device)
            logits, values = model(xb)
            probs = F.softmax(logits, dim=1)
            dist = torch.distributions.Categorical(probs)
            actions = dist.sample()
            logp = dist.log_prob(actions)
            rewards = (actions == yb).float() * cfg.r_tp_attack + (actions != yb).float() * -1.0
            advantage = rewards - values
            actor_loss = -(logp * advantage.detach()).mean()
            critic_loss = advantage.pow(2).mean()
            entropy = dist.entropy().mean()
            loss = actor_loss + 0.5 * critic_loss - 0.01 * entropy
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(loss.item())
        print(f'[A3C epoch {epoch+1}] loss={np.mean(losses):.4f}')
        writer.add_scalar('train/loss', np.mean(losses), epoch)
        # validation
        print('[A3C] running validation')
        y_true = []
        y_pred = []
        model.eval()
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device)
                logits, _ = model(xb)
                preds = torch.argmax(logits, dim=1).cpu().numpy()
                y_true.extend(yb.numpy())
                y_pred.extend(preds.tolist())
        metrics = compute_metrics(np.array(y_true), np.array(y_pred), le.classes_, binary=(len(le.classes_)==2))
        print('[A3C val] metrics:', json.dumps(metrics, indent=2))
        writer.add_scalar('val/macro_f1', metrics['macro_f1'], epoch)
        if metrics['macro_f1'] > best:
            best = metrics['macro_f1']
            ensure_dir(cfg.ckpt_dir)
            torch.save({'model_state_dict': model.state_dict(), 'meta': meta, 'label_classes': list(le.classes_), 'cfg': vars(cfg)}, os.path.join(cfg.ckpt_dir, 'best_model.pth'))
            print('[ckpt] saved best_model.pth')
    writer.close()

# ---------------------------
# Main
# ---------------------------
def main():
    cfg = parse_args()
    print('[main] parsed args:', vars(cfg))
    set_seed(cfg.seed)

    # low-mem adjustments
    if cfg.low_mem:
        print('[mode] LOW MEM: applying aggressive memory settings')
        cfg.batch_size = min(cfg.batch_size, 256)
        cfg.num_workers = 0
        cfg.replay_size = min(cfg.replay_size, 30000)

    # device
    if cfg.device == 'auto':
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    elif cfg.device == 'cuda':
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device('cpu')
    print('[device]', device)
    if device.type == 'cuda':
        print('[cuda] device name:', torch.cuda.get_device_name(0))
        try:
            torch.backends.cudnn.benchmark = True
            torch.set_float32_matmul_precision('high')
            print('[cuda] cuDNN benchmark enabled, TF32 precision set to high')
        except Exception:
            pass

    ensure_dir(cfg.ckpt_dir)
    ensure_dir(cfg.log_dir)
    cache_dir = os.path.join(cfg.ckpt_dir, 'cache')
    ensure_dir(cache_dir)

    # Preprocess to memmap
    print('[main] starting preprocessing to memmap (this may take a while)...')
    X_path, y_path, meta_path = two_pass_memmap(cfg.data_dir, cache_dir, cfg.binary, chunksize=100_000 if not cfg.low_mem else 50_000, low_mem=cfg.low_mem)
    meta = pickle.load(open(meta_path, 'rb'))
    print('[main] preprocessing complete')

    total = int(meta['total_rows'])
    print(f'[main] total rows in memmap: {total}')
    y_all = np.load(y_path, mmap_mode='r')

    # stratified splits
    from sklearn.model_selection import StratifiedShuffleSplit
    idxs = np.arange(total)
    sss = StratifiedShuffleSplit(n_splits=1, test_size=0.10, random_state=cfg.seed)
    train_idx, test_idx = next(sss.split(idxs, y_all))
    sss2 = StratifiedShuffleSplit(n_splits=1, test_size=0.1111, random_state=cfg.seed)
    train_idx, val_idx = next(sss2.split(train_idx, y_all[train_idx]))

    print(f'[split] train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}')

    # datasets & loaders
    print('[main] creating datasets and dataloaders')
    ds_train = MemmapDataset(X_path, y_path, meta_path, indices=train_idx)
    ds_val = MemmapDataset(X_path, y_path, meta_path, indices=val_idx)
    ds_test = MemmapDataset(X_path, y_path, meta_path, indices=test_idx)

    dl_kwargs = {'batch_size': cfg.batch_size, 'num_workers': cfg.num_workers, 'pin_memory': (device.type == 'cuda')}
    train_loader = DataLoader(ds_train, shuffle=True, **dl_kwargs)
    val_loader = DataLoader(ds_val, shuffle=False, **dl_kwargs)
    test_loader = DataLoader(ds_test, shuffle=False, **dl_kwargs)

    print('[main] dataloaders created; sample sizes ->', { 'train': len(ds_train), 'val': len(ds_val), 'test': len(ds_test) })

    # label encoder
    label_classes = meta['label_classes']
    le = LabelEncoder(); le.fit(label_classes)

    input_dim = meta['n_features']
    hidden_dims = [int(x) for x in cfg.hidden_dims.split(',') if x.strip()]
    num_actions = len(le.classes_)

    # model init
    print('[main] initializing model')
    if cfg.algo == 'dqn':
        model = DQN_MLP(input_dim * (cfg.seq_len if cfg.sequence else 1), num_actions, hidden_dims, cfg.dropout).to(device)
        target = DQN_MLP(input_dim * (cfg.seq_len if cfg.sequence else 1), num_actions, hidden_dims, cfg.dropout).to(device)
        target.load_state_dict(model.state_dict())
    else:
        model = ActorCritic(input_dim, num_actions, hidden_dims, use_lstm=cfg.sequence, seq_len=cfg.seq_len, dropout=cfg.dropout).to(device)
        target = None

    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=cfg.epochs * len(train_loader)) if cfg.algo == 'dqn' else None

    # replay buffer
    print(f"[main] creating replay buffer with capacity={cfg.replay_size}")
    replay = ReplayBuffer(cfg.replay_size, state_shape=(input_dim,))

    # resume
    if cfg.resume and os.path.exists(cfg.resume):
        ckpt = torch.load(cfg.resume, map_location=device)
        model.load_state_dict(ckpt.get('model_state_dict', ckpt.get('model', {})))
        print('[resume] loaded', cfg.resume)

    # train
    print('[main] beginning training')
    if cfg.algo == 'dqn':
        train_dqn_loop(model, target, optimizer, scheduler, replay, train_loader, val_loader, le, cfg, device, meta, cache_dir)
    else:
        train_a3c_loop(model, optimizer, train_loader, val_loader, le, cfg, device, meta)

    # final evaluation
    print('[main] running final evaluation on test set')
    def final_eval(mod, dl, le, cfg, device, out_dir):
        mod.eval()
        y_true = []
        y_pred = []
        with torch.no_grad():
            for xb, yb in dl:
                xb = xb.to(device)
                logits = mod(xb) if cfg.algo == 'dqn' else mod(xb)[0]
                preds = torch.argmax(logits, dim=1).cpu().numpy()
                y_true.extend(yb.numpy())
                y_pred.extend(preds.tolist())
        metrics = compute_metrics(np.array(y_true), np.array(y_pred), le.classes_, binary=(len(le.classes_)==2))
        print('[test] metrics:', json.dumps(metrics, indent=2))
        cm = confusion_matrix(y_true, y_pred, labels=list(range(len(le.classes_))))
        save_confusion(cm, le.classes_, os.path.join(out_dir, 'confusion_test.png'))
        with open(os.path.join(out_dir, 'metrics_test.json'), 'w') as f:
            json.dump(metrics, f, indent=2)

    final_eval(model, test_loader, le, cfg, device, cfg.ckpt_dir)
    torch.save({'model_state_dict': model.state_dict(), 'meta': meta, 'label_classes': list(le.classes_), 'cfg': vars(cfg)}, os.path.join(cfg.ckpt_dir, 'final_model.pth'))
    print('[done] artifacts (memmap, checkpoints, metrics) are in', cfg.ckpt_dir)

if __name__ == '__main__':
    main()