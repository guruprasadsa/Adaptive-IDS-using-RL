"""
Data preprocessing utilities for Adaptive IDS

This module contains helper functions for data cleaning, normalization,
and feature engineering used in the intrusion detection pipeline.
"""

import numpy as np
import pandas as pd
from typing import List, Optional


def safe_numeric_conversion(df: pd.DataFrame, columns: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Convert specified columns to numeric, handling errors gracefully.
    
    Args:
        df (pd.DataFrame): Input dataframe
        columns (Optional[List[str]]): Columns to convert. If None, converts all columns.
        
    Returns:
        pd.DataFrame: DataFrame with numeric columns converted
    """
    cols = columns if columns is not None else df.columns
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


def downcast_numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Downcast numeric columns to save memory.
    
    Args:
        df (pd.DataFrame): Input dataframe
        
    Returns:
        pd.DataFrame: DataFrame with downcasted numeric columns
    """
    for c in df.select_dtypes(include=[np.number]).columns:
        df[c] = pd.to_numeric(df[c], downcast='float')
    return df


def clean_col_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean column names consistently with training preprocessing.
    
    This function standardizes column names by:
    - Removing leading/trailing whitespace
    - Replacing spaces, hyphens, and slashes with underscores
    - Removing non-ASCII characters
    
    Args:
        df (pd.DataFrame): Input dataframe
        
    Returns:
        pd.DataFrame: DataFrame with cleaned column names
    """
    cols = df.columns
    new_cols = []
    for col in cols:
        new_col = col.strip().replace(' ', '_').replace('-', '_').replace('/', '_')
        new_col = ''.join(ch for ch in new_col if ord(ch) < 128)
        new_cols.append(new_col)
    df.columns = new_cols
    return df


def normalize_features(X: np.ndarray, means: np.ndarray, stds: np.ndarray, 
                      eps: float = 1e-9) -> np.ndarray:
    """
    Normalize features using precomputed statistics.
    
    Args:
        X (np.ndarray): Input features
        means (np.ndarray): Mean values for each feature
        stds (np.ndarray): Standard deviation values for each feature
        eps (float): Small value to avoid division by zero
        
    Returns:
        np.ndarray: Normalized features
    """
    return ((X - means) / (stds + eps)).astype(np.float32)


def handle_missing_values(df: pd.DataFrame, strategy: str = 'mean') -> pd.DataFrame:
    """
    Handle missing values in the dataframe.
    
    Args:
        df (pd.DataFrame): Input dataframe
        strategy (str): Strategy for handling missing values ('mean', 'median', 'mode', 'drop')
        
    Returns:
        pd.DataFrame: DataFrame with missing values handled
    """
    if strategy == 'mean':
        return df.fillna(df.mean())
    elif strategy == 'median':
        return df.fillna(df.median())
    elif strategy == 'mode':
        return df.fillna(df.mode().iloc[0])
    elif strategy == 'drop':
        return df.dropna()
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def detect_outliers_iqr(df: pd.DataFrame, columns: Optional[List[str]] = None, 
                       factor: float = 1.5) -> pd.DataFrame:
    """
    Detect outliers using the Interquartile Range (IQR) method.
    
    Args:
        df (pd.DataFrame): Input dataframe
        columns (Optional[List[str]]): Columns to check for outliers
        factor (float): IQR factor for outlier detection
        
    Returns:
        pd.DataFrame: Boolean mask indicating outliers
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns
    
    outlier_mask = pd.DataFrame(False, index=df.index, columns=columns)
    
    for col in columns:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - factor * IQR
        upper_bound = Q3 + factor * IQR
        outlier_mask[col] = (df[col] < lower_bound) | (df[col] > upper_bound)
    
    return outlier_mask


def create_feature_combinations(df: pd.DataFrame, feature_pairs: List[tuple]) -> pd.DataFrame:
    """
    Create new features by combining existing ones.
    
    Args:
        df (pd.DataFrame): Input dataframe
        feature_pairs (List[tuple]): List of (col1, col2, operation) tuples
        
    Returns:
        pd.DataFrame: DataFrame with new combined features
    """
    new_df = df.copy()
    
    for col1, col2, operation in feature_pairs:
        if col1 in df.columns and col2 in df.columns:
            if operation == 'add':
                new_df[f'{col1}_plus_{col2}'] = df[col1] + df[col2]
            elif operation == 'multiply':
                new_df[f'{col1}_times_{col2}'] = df[col1] * df[col2]
            elif operation == 'divide':
                new_df[f'{col1}_div_{col2}'] = df[col1] / (df[col2] + 1e-9)
            elif operation == 'subtract':
                new_df[f'{col1}_minus_{col2}'] = df[col1] - df[col2]
    
    return new_df
