
from sklearn.feature_extraction.text import CountVectorizer
import numpy as np
import pandas as pd

def generate(topics_df, cluster_column='cluster', text_column='text', n_terms=2):
   """
   Extract cluster labels using Class-based TF-IDF (C-TF-IDF).
   
   Parameters:
   -----------
   topics_df : pd.DataFrame
       DataFrame containing Bluesky posts with cluster assignments
   cluster_column : str, default='cluster'
       Name of column containing cluster IDs/labels
   text_column : str, default='text' 
       Name of column containing Bluesky post text to analyze
   n_terms : int, default=1
       Number of top distinctive terms to use for each cluster label
       
   Returns:
   --------
   pd.DataFrame
       Original DataFrame with added 'label' column containing cluster labels
       Also renames 'UMAP1' -> 'umap_1_mean' and 'UMAP2' -> 'umap_2_mean' if present
   """
 
   
   # Create a copy to avoid modifying the original
   result_df = topics_df.copy()
   
   # Group documents by cluster with UMAP coordinates
   clusters_df = topics_df.groupby(cluster_column).agg({
       text_column: ' '.join,
       'UMAP1': 'mean',
       'UMAP2': 'mean'
   }).reset_index()
   
   # Extract cluster documents
   cluster_docs = clusters_df.set_index(cluster_column)[text_column].to_dict()
   
   # Prepare data
   cluster_ids = sorted(cluster_docs.keys())
   documents = [cluster_docs[cid] for cid in cluster_ids]
   
   # Vectorize
   vectorizer = CountVectorizer(
       stop_words='english',
       ngram_range=(1, 2),
       min_df=1,  # Keep all terms
       max_features=10000
   )
   
   count_matrix = vectorizer.fit_transform(documents)
   feature_names = vectorizer.get_feature_names_out()
   
   # C-TF-IDF calculation
   tf = count_matrix.toarray()
   tf = tf / tf.sum(axis=1, keepdims=True)  # Normalize by cluster size
   
   # IDF: log(total clusters / clusters containing term)
   df = np.count_nonzero(tf, axis=0)
   idf = np.log(len(cluster_ids) / df)
   
   c_tfidf = tf * idf
   
   # Extract labels for each cluster
   cluster_labels = {}
   for i, cluster_id in enumerate(cluster_ids):
       top_indices = c_tfidf[i].argsort()[-n_terms:][::-1]
       cluster_labels[cluster_id] = ' '.join([feature_names[idx] for idx in top_indices])
   
   # Add labels to the dataframe
   result_df['label'] = result_df[cluster_column].map(cluster_labels)
   
   # Add cluster summary with UMAP means (like your pattern)
   clusters_df['label'] = clusters_df[cluster_column].map(cluster_labels)
   clusters_df.rename(columns={
       'UMAP1': 'umap_1_mean', 
       'UMAP2': 'umap_2_mean',
       cluster_column: 'Cluster'
   }, inplace=True)
   
   # Rename columns in result_df if they exist
   column_mapping = {'UMAP1': 'umap_1_mean', 'UMAP2': 'umap_2_mean'}
   result_df.rename(columns=column_mapping, inplace=True)
   
   # Return the cluster summary DataFrame (like your pattern)
   return clusters_df

def label_bluesky_posts(posts, cluster_column='cluster', n_terms=2):
    """
    Convenience function to label Bluesky posts directly from post list
    
    Parameters:
    -----------
    posts : list of dict
        List of Bluesky posts from client.fetch_popular_posts()
    cluster_column : str, default='cluster' 
        Column name for cluster assignments (set by encoder)
    n_terms : int, default=2
        Number of terms to use for labels
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with cluster summaries (grouped like your pattern)
    """
    # Convert posts to DataFrame
    df = pd.DataFrame(posts)
    
    # Map encoder cluster columns to expected names
    if 'topic_cluster' in df.columns:
        df[cluster_column] = df['topic_cluster']
    
    # Use the main generate function
    return generate(df, cluster_column=cluster_column, text_column='text', n_terms=n_terms)