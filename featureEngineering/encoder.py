from sentence_transformers import SentenceTransformer
from umap import UMAP
from sklearn.decomposition import PCA
import torch
import numpy as np
import pickle
import os
import tensorflow as tf

def run(posts,
        model_name='all-MiniLM-L6-v2',
        batch_size=100,
        umap_components=5,
        random_state=42,
        min_dist=0.5,
        n_neighbors=15,
        device=None,
        umap_model_path=None,
        use_parametric=False,
        skip_embedding=False,
        use_pca=True,
        pca_components=50):
    """
    Efficiently encode Bluesky post text in batches using sentence transformers,
    and add UMAP dimensionality reduction using either standard UMAP or saved Parametric UMAP.
    
    Parameters:
    -----------
    posts : list of dict
        List of Bluesky post dictionaries, each containing at least a 'text' key
        If skip_embedding=True, should contain 'embedding' key instead
    model_name : str, optional
        Name of the SentenceTransformer model to use (default: 'all-MiniLM-L6-v2')
    batch_size : int, optional
        Number of posts to process in each batch (default: 100)
    umap_components : int, optional
        Number of dimensions for UMAP reduction (default: 2)
    random_state : int, optional
        Random seed for UMAP for reproducibility (default: 42)
    min_dist : float, optional
        UMAP min_dist parameter controlling how tightly points are packed (default: 0.3)
    n_neighbors : int, optional
        UMAP n_neighbors parameter controlling local versus global structure (default: 8)
    device : str, optional
        Device to run the model on ('cpu', 'cuda', 'mps', etc.)
        If None, will use CUDA if available, otherwise CPU
    umap_model_path : str, optional
        Path to saved Parametric UMAP model (e.g., 'data/umap_model/model.pkl')
        If provided, will load and use this trained model instead of creating new one
    use_parametric : bool, optional
        Whether to use parametric UMAP. If True and umap_model_path is None, 
        will create new parametric UMAP (default: False)
    skip_embedding : bool, optional
        If True, skip embedding calculation and use existing 'embedding' field from posts.
        Useful when posts already contain precomputed embeddings (default: False)
    use_pca : bool, optional
        Whether to apply PCA before UMAP to reduce dimensionality and compress outliers (default: True)
    pca_components : int, optional
        Number of PCA components to use (default: 50)
        
    Returns:
    --------
    list of dict
        The input posts with 'embedding' and 'umap_embedding' fields added to each post that has text
    """
    
    if skip_embedding:
        # Use existing embeddings
        valid_indices = []
        all_embeddings = []
        
        for i, post in enumerate(posts):
            embedding = post.get('embedding')
            if embedding is not None:
                valid_indices.append(i)
                # Convert to numpy array if it's a list
                if isinstance(embedding, list):
                    embedding_np = np.array(embedding)
                else:
                    embedding_np = embedding
                all_embeddings.append(embedding_np)
        
        if all_embeddings:
            all_embeddings = np.vstack(all_embeddings)
            print(f"✅ Using existing embeddings for {len(all_embeddings)} posts")
        else:
            print("⚠️  No valid embeddings found in posts. Please check your data.")
            return posts
    else:
        # Calculate new embeddings (original behavior)
        # Load sentence transformer model
        model = SentenceTransformer(model_name)
        
        # Set device if specified
        if device:
            model = model.to(device)
        
        # Extract post text (skipping None or empty text)
        valid_indices = []
        texts_to_encode = []
        
        for i, post in enumerate(posts):
            text = post.get('text')
            if text and isinstance(text, str) and text.strip():
                valid_indices.append(i)
                texts_to_encode.append(text)
        
        # Process post texts in batches to get original embeddings
        original_embeddings = []
        
        for i in range(0, len(texts_to_encode), batch_size):
            batch = texts_to_encode[i:i+batch_size]
            batch_embeddings = model.encode(
                batch, 
                convert_to_tensor=True, 
                normalize_embeddings=True,
                show_progress_bar=False
            )
            
            # Convert to numpy for storage
            if isinstance(batch_embeddings, torch.Tensor):
                batch_embeddings_np = batch_embeddings.cpu().numpy()
            else:
                batch_embeddings_np = np.array(batch_embeddings)
                
            original_embeddings.append(batch_embeddings_np)
        
        # Combine all batches
        if original_embeddings:
            all_embeddings = np.vstack(original_embeddings)
            
            # Store embeddings in posts if we calculated them
            original_embeddings_list = all_embeddings.tolist()
            for idx, post_idx in enumerate(valid_indices):
                posts[post_idx]['embedding'] = original_embeddings_list[idx]
        else:
            print("⚠️  No valid post text found for embedding.")
            return posts
    
    # Apply PCA before UMAP if requested
    if len(all_embeddings) > 0 and use_pca and all_embeddings.shape[1] > pca_components:
        print(f"🔄 Applying PCA to reduce from {all_embeddings.shape[1]} to {pca_components} dimensions...")
        pca = PCA(n_components=pca_components, random_state=random_state)
        all_embeddings = pca.fit_transform(all_embeddings)
        print(f"✅ PCA explained variance ratio: {pca.explained_variance_ratio_.sum():.3f}")
    
    # Apply UMAP dimensionality reduction
    if len(all_embeddings) > 0:
        # Choose UMAP approach based on parameters
        if umap_model_path and os.path.exists(umap_model_path):
            # Load saved Parametric UMAP model
            print(f"Loading saved Parametric UMAP model from: {umap_model_path}")
            try:
                import tensorflow.compat.v1 as tf_v1
                tf_v1.disable_v2_behavior()
                umap_instance = tf.keras.models.load_model(umap_model_path, compile=False)
            except:
                print("Legacy loading failed, please retrain the model")
            
            # Transform using the loaded model
            umap_embeddings = umap_instance.transform(all_embeddings)
            print(f"✅ Applied saved Parametric UMAP to {len(all_embeddings)} embeddings")
            
        elif use_parametric:
            # Create new Parametric UMAP
            print("Creating new Parametric UMAP...")
            from umap.parametric_umap import ParametricUMAP
            
            umap_instance = ParametricUMAP(
                n_components=umap_components,
                random_state=random_state,
                min_dist=min_dist,
                n_neighbors=n_neighbors,
                batch_size=min(batch_size, 128)  # Use smaller batch for memory efficiency
            )
            umap_embeddings = umap_instance.fit_transform(all_embeddings)
            print(f"✅ Created new Parametric UMAP for {len(all_embeddings)} embeddings")
            
        else:
            # Use standard UMAP (original behavior)
            print("Using standard UMAP...")
            umap_instance = UMAP(
                n_components=umap_components,
                random_state=random_state,
                min_dist=min_dist,
                n_neighbors=n_neighbors,
                spread=1.5,
                metric='cosine'
            )
            umap_embeddings = umap_instance.fit_transform(all_embeddings)
            print(f"✅ Applied standard UMAP to {len(all_embeddings)} embeddings")
        
        # Convert UMAP embeddings to list format and assign to posts
        umap_embeddings_list = umap_embeddings.tolist()
        
        for idx, post_idx in enumerate(valid_indices):
            for component_idx in range(umap_components):
                posts[post_idx][f'UMAP{component_idx + 1}'] = umap_embeddings_list[idx][component_idx]
    
    return posts