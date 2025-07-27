
**[View Live Visualization](https://muhammadomarmuhdhar.github.io/atproto-synoptic-chart/visualization/)**

# Bluesky Synoptic Chart

A real-time visualization of trending topics on Bluesky, showing how conversations cluster and evolve over time using UMAP dimensionality reduction.

## What This Is

This project creates an interactive "weather map" of social media discussions by:
- Collecting posts from Bluesky's "What's Hot Classic" feed
- Using machine learning (Transformer Embeddings & UMAP) to map similar posts together in 2D space
- Generating density contours showing topic "hotspots" 
- Animating changes over time to reveal conversation evolution


## File Structure

```
├── ETL/                          # Data pipeline
│   ├── etl.py                   # Main ETL orchestrator
│   ├── clients/                 # API clients
│   │   ├── bluesky.py          # Bluesky data collection
│   │   └── bigQuery.py         # BigQuery storage
│   ├── feature_engineering/     # ML processing
│   │   ├── encoder.py          # UMAP embedding generation
│   │   └── density.py          # Density calculation
│   └── labels/                  # Topic labeling (experimental)
├── data/                        # Generated data files
│   ├── posts.json              # Recent posts with coordinates
│   ├── density_data.json       # Density contours over time
│   └── last_update.json        # Export metadata
└── visualization/               # Web interface
    ├── index.html              # Interactive D3.js visualization
    └── script.js               # Animation and interaction logic
```

## How It Works

### 1. Data Collection + ML Processing (Every 10 minutes)
- Fetches 100 popular posts from Bluesky API
- Filters for posts with substantial content (30+ characters)
- Generates UMAP embeddings using [pre-trained model](https://huggingface.co/notMuhammad/atproto-topic-umap)
- Maps posts to 5D coordinates, uses first 2 dimensions for visualization
- Stores in BigQuery with metadata and coordinates

### 2. Density Calculation (Every 30 minutes)
- Creates 2D density grid from recent post coordinates
- Identifies "hotspots" where similar conversations concentrate
- Uses Gaussian kernels for smooth contour generation

### 3. Visualization Export (Every hour)
- Exports last 24 hours of posts and density data
- Automatically commits JSON files to GitHub
- Updates live visualization via GitHub Pages

### 4. Interactive Display
- **Play/pause**: Animate through time to see topic evolution
- **Hover**: View individual posts with author and timestamp
- **Zoom/pan**: Explore different areas of the topic landscape
- **Color contours**: Show conversation density (blue = more activity)

## Technical Stack

- **Data Pipeline**: Python, Google Cloud Functions, BigQuery
- **ML**: UMAP, sentence-transformers, Gaussian density estimation
- **Visualization**: D3.js, HTML5 Canvas
- **Hosting**: GitHub Pages
- **APIs**: ATProto/Bluesky

## Setup

1. Configure environment variables for BigQuery and Bluesky API
2. Deploy ETL pipeline to Google Cloud Functions
3. Enable GitHub Pages on the repository
4. ETL runs automatically, updating visualization hourly

The visualization reveals how trending topics emerge, merge, and evolve throughout the day on Bluesky.

## Future

Once ATProto gets built out, this system will expand to track conversations across multiple social platforms. Currently it only monitors Bluesky, specifically pulling from the "What's Hot Classic" feed to capture trending discussions.
