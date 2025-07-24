import pandas as pd
import numpy as np
import json
from scipy import ndimage
import matplotlib.pyplot as plt
from matplotlib.contour import QuadContourSet
import matplotlib.patches as patches

def create_contour_paths(density_grid, x_coords, y_coords, levels=10):
    """
    Generate contour paths using matplotlib and convert to D3-compatible format.
    """
    # Create matplotlib figure (won't be displayed)
    fig, ax = plt.subplots(figsize=(1, 1))
    
    # Create contour plot
    X, Y = np.meshgrid(x_coords, y_coords)
    contour_set = ax.contour(X, Y, density_grid, levels=levels)
    
    # Extract contour paths
    contour_data = []
    
    for i, collection in enumerate(contour_set.collections):
        level = contour_set.levels[i]
        paths = []
        
        for path in collection.get_paths():
            # Convert matplotlib path to list of coordinates
            vertices = path.vertices
            if len(vertices) > 2:  # Only include paths with sufficient points
                path_coords = [{"x": float(v[0]), "y": float(v[1])} for v in vertices]
                paths.append(path_coords)
        
        if paths:  # Only add if there are valid paths
            contour_data.append({
                "level": float(level),
                "paths": paths
            })
    
    plt.close(fig)  # Clean up
    return contour_data

def preprocess_density_data(csv_file, output_file, num_levels=10):
    """
    Preprocess the density CSV data and create optimized JSON with pre-calculated contours.
    """
    print("Loading CSV data...")
    df = pd.read_csv(csv_file)
    
    # Convert to numeric
    df['x'] = pd.to_numeric(df['x'])
    df['y'] = pd.to_numeric(df['y']) 
    df['density'] = pd.to_numeric(df['density'])
    
    # Get unique intervals
    intervals = sorted(df['interval_name'].unique())
    print(f"Found {len(intervals)} intervals: {intervals}")
    
    # Get grid dimensions from first interval
    first_interval_data = df[df['interval_name'] == intervals[0]]
    unique_x = sorted(first_interval_data['x'].unique())
    unique_y = sorted(first_interval_data['y'].unique())
    
    grid_width = len(unique_x)
    grid_height = len(unique_y)
    
    print(f"Grid dimensions: {grid_width} x {grid_height}")
    
    # Prepare output data structure
    output_data = {
        "metadata": {
            "grid_width": grid_width,
            "grid_height": grid_height,
            "x_extent": [float(min(unique_x)), float(max(unique_x))],
            "y_extent": [float(min(unique_y)), float(max(unique_y))],
            "intervals": intervals,
            "contour_levels": num_levels
        },
        "intervals": {}
    }
    
    # Process each interval
    for i, interval in enumerate(intervals):
        print(f"Processing {interval} ({i+1}/{len(intervals)})...")
        
        interval_data = df[df['interval_name'] == interval]
        
        # Create density grid
        density_grid = np.zeros((grid_height, grid_width))
        
        for _, row in interval_data.iterrows():
            try:
                x_idx = unique_x.index(row['x'])
                y_idx = unique_y.index(row['y'])
                density_grid[y_idx, x_idx] = row['density']
            except ValueError:
                continue  # Skip if coordinates not found
        
        # Calculate density statistics
        density_stats = {
            "min": float(np.min(density_grid)),
            "max": float(np.max(density_grid)),
            "mean": float(np.mean(density_grid)),
            "std": float(np.std(density_grid))
        }
        
        # Generate contour paths
        try:
            contour_paths = create_contour_paths(
                density_grid, 
                unique_x, 
                unique_y, 
                levels=num_levels
            )
        except Exception as e:
            print(f"Warning: Could not generate contours for {interval}: {e}")
            contour_paths = []
        
        # Store interval data
        output_data["intervals"][interval] = {
            "density_stats": density_stats,
            "contour_paths": contour_paths,
            "posts_count": int(interval_data['posts_count'].iloc[0]) if 'posts_count' in interval_data.columns else 0
        }
        
        print(f"  - Generated {len(contour_paths)} contour levels")
    
    # Calculate global density extent for color scale
    all_densities = df['density'].values
    output_data["metadata"]["density_extent"] = [float(np.min(all_densities)), float(np.max(all_densities))]
    
    # Save to JSON
    print(f"Saving preprocessed data to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    # Print summary
    file_size_mb = pd.read_csv(csv_file).memory_usage(deep=True).sum() / 1024 / 1024
    with open(output_file, 'r') as f:
        json_size_mb = len(f.read().encode('utf-8')) / 1024 / 1024
    
    print(f"\nPreprocessing complete!")
    print(f"Original CSV size: {file_size_mb:.1f} MB")
    print(f"Optimized JSON size: {json_size_mb:.1f} MB")
    print(f"Size reduction: {((file_size_mb - json_size_mb) / file_size_mb * 100):.1f}%")
    
    return output_data

if __name__ == "__main__":
    # Preprocess the data
    preprocess_density_data(
        "density_30min_intervals.csv", 
        "density_contours_optimized.json",
        num_levels=12
    )