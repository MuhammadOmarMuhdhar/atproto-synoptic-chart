import pandas as pd
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.preprocessing import StandardScaler

def generate(df, 
        umap_columns=['UMAP1', 'UMAP2', 'UMAP3', 'UMAP4', 'UMAP5'], 
        n_clusters=7, 
        linkage='ward',
        scale_features=True):
    """
    Apply Agglomerative clustering to a DataFrame with UMAP or other dimensional reduction features.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Input DataFrame containing dimensional reduction features
    umap_columns : list, optional
        List of column names to use for clustering (default: ['UMAP1', 'UMAP2', 'UMAP3', 'UMAP4', 'UMAP5'])
    n_clusters : int, optional
        Number of clusters to create (default: 7)
    linkage : str, optional
        Linkage criterion ('ward', 'complete', 'average', 'single') (default: 'ward')
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
    
    # Apply Agglomerative clustering
    clusterer = AgglomerativeClustering(
        n_clusters=n_clusters,
        linkage=linkage
    )
    
    # Predict clusters and add to DataFrame
    plot_df['cluster'] = clusterer.fit_predict(clustering_data)
    
    return plot_df