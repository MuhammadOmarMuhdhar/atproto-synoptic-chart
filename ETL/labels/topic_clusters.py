import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

def generate(df, 
        umap_columns=['UMAP1', 'UMAP2', 'UMAP3', 'UMAP4', 'UMAP5'], 
        n_clusters=7, 
        random_state=42, 
        scale_features=True):
    """
    Apply K-means clustering to a DataFrame with UMAP or other dimensional reduction features.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Input DataFrame containing dimensional reduction features
    umap_columns : list, optional
        List of column names to use for clustering (default: ['UMAP1', 'UMAP2'])
    n_clusters : int, optional
        Number of clusters to create (default: 7)
    random_state : int, optional
        Seed for reproducibility (default: 42)
    scale_features : bool, optional
        Whether to scale features before clustering (default: True)
    
    Returns:
    --------
    pandas.DataFrame
        Original DataFrame with an additional 'cluster' column
    """
    # Create a copy to avoid modifying the original DataFrame
    plot_df = df.copy()
    
    # Select the specified columns for clustering
    clustering_data = plot_df[umap_columns]
    
    # Optional: Scale the features
    if scale_features:
        scaler = StandardScaler()
        clustering_data = scaler.fit_transform(clustering_data)
    
    # Apply K-means clustering
    kmeans = KMeans(
        n_clusters=n_clusters, 
        random_state=random_state, 
        n_init=10  # Recommended default to avoid warnings
    )
    
    # Predict clusters and add to DataFrame
    plot_df['cluster'] = kmeans.fit_predict(clustering_data)
    
    return plot_df