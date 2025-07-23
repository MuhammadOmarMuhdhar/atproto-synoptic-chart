import numpy as np
import pandas as pd
from scipy import ndimage

def _calculate_dynamic_resolution(data_size, base_resolution=100):
    """
    Calculate optimal resolution based on data size.
    Less data = higher resolution for better detail
    More data = lower resolution for performance
    """
    if data_size < 100:
        resolution = min(100, base_resolution * 2)  # High detail for small datasets
    elif data_size < 500:
        resolution = min(80, int(base_resolution * 1.5))
    elif data_size < 2000:
        resolution = base_resolution  # Use default
    elif data_size < 10000:
        resolution = max(30, int(base_resolution * 0.8))
    elif data_size < 50000:
        resolution = max(25, int(base_resolution * 0.6))
    else:
        resolution = max(20, int(base_resolution * 0.4))  # Low resolution for huge datasets
    
    return resolution

def _stratified_spatial_sample(df, n_sample, x_col, y_col):
    """
    Stratified spatial sampling that preserves the spatial distribution of points.
    """
    try:
        # Create spatial grid for stratification
        n_bins = max(10, min(50, int(np.sqrt(n_sample / 10))))  # Adaptive grid size
        
        x_bins = pd.cut(df[x_col], bins=n_bins, labels=False)
        y_bins = pd.cut(df[y_col], bins=n_bins, labels=False)
        
        # Create stratification groups
        df_temp = df.copy()
        df_temp['spatial_bin'] = x_bins * n_bins + y_bins
        
        # Sample proportionally from each spatial bin
        sampled_dfs = []
        bin_counts = df_temp['spatial_bin'].value_counts()
        
        for bin_id, count in bin_counts.items():
            bin_data = df_temp[df_temp['spatial_bin'] == bin_id]
            # Calculate proportional sample size for this bin
            bin_sample_size = max(1, int((count / len(df)) * n_sample))
            
            if len(bin_data) <= bin_sample_size:
                sampled_dfs.append(bin_data)
            else:
                sampled_bin = bin_data.sample(n=bin_sample_size, random_state=42)
                sampled_dfs.append(sampled_bin)
        
        # Combine all sampled bins
        sampled_df = pd.concat(sampled_dfs, ignore_index=True)
        
        # If we're still over target, randomly sample down
        if len(sampled_df) > n_sample:
            sampled_df = sampled_df.sample(n=n_sample, random_state=42)
        
        # Remove temporary column
        sampled_df = sampled_df.drop('spatial_bin', axis=1)
        
        return sampled_df
        
    except Exception as e:
        # Fallback to simple random sampling
        print(f"Stratified sampling failed, using random sampling: {e}")
        return df.sample(n=min(n_sample, len(df)), random_state=42)

def model(df, x_col='UMAP1', y_col='UMAP2', base_resolution=100, sigma=1.5,
          x_min=None, x_max=None, y_min=None, y_max=None, verbose=False):
    """
    Histogram-based density estimation with intelligent sampling and dynamic resolution.
    Matches the algorithm used in heatmap.py for consistency.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame containing the data points
    x_col : str
        Column name for x coordinates (default: 'UMAP1')
    y_col : str
        Column name for y coordinates (default: 'UMAP2')
    base_resolution : int
        Base resolution for the grid (will be adjusted dynamically)
    sigma : float
        Gaussian smoothing parameter
    x_min, x_max, y_min, y_max : float
        Bounds for the density grid. If None, calculated from data
    verbose : bool
        Whether to print debug information
    """
    if len(df) < 10:
        if verbose:
            print("Insufficient data for histogram density calculation")
        return None
        
    try:
        # Define sampling thresholds
        data_size = len(df)
        
        # Calculate dynamic resolution based on data size
        dynamic_resolution = _calculate_dynamic_resolution(data_size, base_resolution)
        
        if data_size < 1000:
            sample_pct = 1.0  # Use all data
            max_sample = data_size
        elif data_size < 5000:
            sample_pct = 0.8  # 80%
            max_sample = int(data_size * sample_pct)
        elif data_size < 20000:
            sample_pct = 0.5  # 50%
            max_sample = int(data_size * sample_pct)
        elif data_size < 50000:
            sample_pct = 0.3  # 30%
            max_sample = int(data_size * sample_pct)
        elif data_size < 100000:
            sample_pct = 0.2  # 20%
            max_sample = int(data_size * sample_pct)
        else:
            sample_pct = 0.1  # 10%
            max_sample = int(data_size * sample_pct)
        
        if verbose:
            print(f"Using sample percentage: {sample_pct*100:.1f}% ({max_sample} points) with resolution {dynamic_resolution}")
        
        # Smart sampling that preserves spatial distribution
        if sample_pct < 1.0:
            sampled_df = _stratified_spatial_sample(df, max_sample, x_col, y_col)
        else:
            sampled_df = df
        
        x = sampled_df[x_col].values
        y = sampled_df[y_col].values
        
        # Use provided bounds or calculate from data
        if x_min is None:
            x_min, x_max = x.min(), x.max()
            y_min, y_max = y.min(), y.max()
            # Add padding
            x_padding = (x_max - x_min) * 0.1
            y_padding = (y_max - y_min) * 0.1
            x_min -= x_padding
            x_max += x_padding
            y_min -= y_padding
            y_max += y_padding
        
        # Create 2D histogram with DYNAMIC resolution
        hist, x_edges, y_edges = np.histogram2d(
            x, y, 
            bins=dynamic_resolution,
            range=[[x_min, x_max], [y_min, y_max]]
        )
        
        # Apply Gaussian smoothing using FFT
        density = ndimage.gaussian_filter(hist.T, sigma=sigma, mode='constant')
        
        # Scale density to account for sampling
        if sample_pct < 1.0:
            density = density / sample_pct
        
        # Create coordinate meshes
        x_centers = (x_edges[:-1] + x_edges[1:]) / 2
        y_centers = (y_edges[:-1] + y_edges[1:]) / 2
        xi, yi = np.meshgrid(x_centers, y_centers)
        
        if verbose:
            print(f"Successfully calculated histogram density with range: {density.min():.4f} - {density.max():.4f}")
        
        return {
            'x': xi,
            'y': yi,
            'density': density,
            'x_flat': xi.ravel(),
            'y_flat': yi.ravel(),
            'density_flat': density.ravel()
        }
        
    except Exception as e:
        print(f"Error in density calculation: {e}")
        return None