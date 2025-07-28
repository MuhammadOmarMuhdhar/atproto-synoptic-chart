from sentence_transformers import SentenceTransformer
from umap import UMAP
from sklearn.decomposition import PCA
import torch
import numpy as np
import pickle
import os

def run(posts,
        model_name='sentence-transformers/all-mpnet-base-v2',
        batch_size=100,
        umap_components=5,
        random_state=42,
        min_dist=0.0,
        n_neighbors=15,
        spread=20,
        device=None,
        umap_model_path=None,
        use_parametric=False,
        skip_embedding=False,
        use_pca=True,
        pca_components=50,
        save_parametric_model_path=None):
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
    save_parametric_model_path : str, optional
        Path to save the trained Parametric UMAP model when use_parametric=True and umap_model_path=None
        Only used when creating a new parametric model (default: None)
        
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
        if umap_model_path:
            # Check if it's a cloud storage path, hugging face path, or local path
            is_cloud_path = umap_model_path.startswith('gs://')
            is_hf_path = umap_model_path.startswith('hf://')
            path_exists = is_cloud_path or is_hf_path or os.path.exists(umap_model_path)
            
            if path_exists:
                # Load saved Parametric UMAP model
                print(f"Loading saved Parametric UMAP model from: {umap_model_path}")
                try:
                    if is_hf_path:
                        # For Hugging Face, download model to local cache
                        from huggingface_hub import snapshot_download
                        
                        # Parse repo_id from hf:// URL (e.g., hf://notMuhammad/atproto-topic-umap)
                        repo_id = umap_model_path.replace('hf://', '')
                        
                        # Download model to local cache
                        local_model_path = snapshot_download(
                            repo_id=repo_id,
                            repo_type="model"
                        )
                        print(f"Downloaded model from Hugging Face to: {local_model_path}")
                        
                        # Load from local cache directory
                        from umap.parametric_umap import load_ParametricUMAP
                        umap_instance = load_ParametricUMAP(os.path.join(local_model_path, "model"))
                        
                    elif is_cloud_path:
                        # For cloud storage, download model to temp directory first
                        import tempfile
                        from google.cloud import storage
                        
                        temp_dir = tempfile.mkdtemp()
                        
                        # Parse bucket and path from gs:// URL
                        path_parts = umap_model_path.replace('gs://', '').split('/', 1)
                        bucket_name = path_parts[0]
                        model_prefix = path_parts[1] if len(path_parts) > 1 else ''
                        
                        # Download model files
                        client = storage.Client()
                        bucket = client.bucket(bucket_name)
                        
                        # List and download all model files
                        blobs = bucket.list_blobs(prefix=model_prefix)
                        local_model_path = None
                        
                        for blob in blobs:
                            if blob.name.endswith('/'):
                                continue  # Skip directories
                            
                            # Create local file path
                            local_file_path = os.path.join(temp_dir, os.path.basename(blob.name))
                            blob.download_to_filename(local_file_path)
                            print(f"Downloaded {blob.name} to {local_file_path}")
                            
                            # Set model path to directory for loading
                            if local_model_path is None:
                                local_model_path = temp_dir
                        
                        # Load from local temp directory
                        from umap.parametric_umap import load_ParametricUMAP
                        umap_instance = load_ParametricUMAP(local_model_path)
                    else:
                        # Load from local path
                        from umap.parametric_umap import load_ParametricUMAP
                        umap_instance = load_ParametricUMAP(umap_model_path)
                        
                except Exception as e:
                    print(f"Failed to load model: {e}")
                    print("Creating new Parametric UMAP instead...")
                    # Fall through to create new model
                    umap_instance = None
                
                if umap_instance is not None:
                    # Transform using the loaded model
                    umap_embeddings = umap_instance.transform(all_embeddings)
                    print(f"✅ Applied saved Parametric UMAP to {len(all_embeddings)} embeddings")
                else:
                    # Create new model if loading failed
                    print("Creating new Parametric UMAP...")
                    from umap.parametric_umap import ParametricUMAP
                    
                    umap_instance = ParametricUMAP(
                        n_components=umap_components,
                        random_state=random_state,
                        min_dist=min_dist,
                        n_neighbors=n_neighbors,
                        spread=spread,
                        batch_size=min(batch_size, 128)
                    )
                    umap_embeddings = umap_instance.fit_transform(all_embeddings)
                    print(f"✅ Created new Parametric UMAP for {len(all_embeddings)} embeddings")
            else:
                print(f"Model path {umap_model_path} does not exist, creating new model")
                # Create new model
                print("Creating new Parametric UMAP...")
                from umap.parametric_umap import ParametricUMAP
                
                umap_instance = ParametricUMAP(
                    n_components=umap_components,
                    random_state=random_state,
                    min_dist=min_dist,
                    n_neighbors=n_neighbors,
                    spread=spread,
                    batch_size=min(batch_size, 128)
                )
                umap_embeddings = umap_instance.fit_transform(all_embeddings)
                print(f"✅ Created new Parametric UMAP for {len(all_embeddings)} embeddings")
            
        elif use_parametric:
            # Create new Parametric UMAP
            print("Creating new Parametric UMAP...")
            from umap.parametric_umap import ParametricUMAP
            
            umap_instance = ParametricUMAP(
                n_components=umap_components,
                random_state=random_state,
                min_dist=min_dist,
                n_neighbors=n_neighbors,
                spread=spread,
                batch_size=min(batch_size, 128)
                 )
            

            umap_embeddings = umap_instance.fit_transform(all_embeddings)
            print(f"✅ Created new Parametric UMAP for {len(all_embeddings)} embeddings")

            # Save the trained model if requested
            if save_parametric_model_path:
                os.makedirs(os.path.dirname(save_parametric_model_path), exist_ok=True)
                try:
                    umap_instance.save(save_parametric_model_path)
                    print(f"✅ Saved Parametric UMAP model to {save_parametric_model_path}")
                except Exception as e:
                    print(f"⚠️ Failed to save Parametric UMAP model: {e}")
            
        else:
            # Use standard UMAP (original behavior)
            print("Using standard UMAP...")
            umap_instance = UMAP(
                n_components=umap_components,
                random_state=random_state,
                min_dist=min_dist,
                n_neighbors=n_neighbors,
                spread=spread,
                metric='euclidean',
            )
            umap_embeddings = umap_instance.fit_transform(all_embeddings)
            print(f"✅ Applied standard UMAP to {len(all_embeddings)} embeddings")
        
        # Convert UMAP embeddings to list format and assign to posts
        umap_embeddings_list = umap_embeddings.tolist()
        
        for idx, post_idx in enumerate(valid_indices):
            for component_idx in range(umap_components):
                posts[post_idx][f'UMAP{component_idx + 1}'] = umap_embeddings_list[idx][component_idx]
    
    return posts