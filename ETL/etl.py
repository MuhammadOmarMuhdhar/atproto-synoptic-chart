import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
import sys

from ETL.clients.bluesky import Client as BlueskyClient
from ETL.clients.bigQuery import Client as BigQueryClient
from ETL.feature_engineering import encoder
from ETL.feature_engineering import density
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

class ATProtoETL:
    """
    AT Proto Synoptic Chart ETL Pipeline
    Collects Bluesky posts, generates UMAP embeddings, and calculates density grids.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Load environment variables
        self.bigquery_credentials = json.loads(os.environ['BIGQUERY_CREDENTIALS_JSON'])
        self.project_id = os.environ['BIGQUERY_PROJECT_ID']
        self.dataset_id = os.environ['BIGQUERY_DATASET_ID']
        self.posts_table = os.environ['BIGQUERY_TABLE_ID_POSTS']
        self.density_table = os.environ['BIGQUERY_TABLE_ID_DENSITY']
        
        # Initialize clients
        self.bluesky_client = None
        self.bigquery_client = None
        
        # ETL configuration
        self.batch_size = 100
        self.density_interval_minutes = 30
        self.export_interval_minutes = 60
        self.essential_columns = [
            'uri', 'text', 'author', 'like_count', 'reply_count', 'repost_count', 
            'created_at', 'collected_at', 'UMAP1', 'UMAP2', 'UMAP3', 'UMAP4', 'UMAP5'
        ]
    
    def initialize_clients(self):
        """Initialize Bluesky and BigQuery clients"""
        self.logger.info("Initializing clients")
        
        self.bluesky_client = BlueskyClient()
        self.bigquery_client = BigQueryClient(self.bigquery_credentials, self.project_id)
        
        # Authenticate with Bluesky
        if not self.bluesky_client.authenticate():
            raise Exception("Failed to authenticate with Bluesky API")
        
        self.logger.info("Successfully authenticated with all clients")
    
    def extract_posts(self):
        """Extract posts from Bluesky"""
        self.logger.info("Extracting posts from Bluesky")
        
        posts = self.bluesky_client.fetch_popular_posts(
            limit=self.batch_size,
            min_length=30
        )
        
        if not posts:
            self.logger.warning("No posts retrieved from Bluesky")
            return None
        
        self.logger.info(f"Retrieved {len(posts)} posts from Bluesky")
        return posts
    
    def transform_posts(self, posts):
        """Transform posts by adding UMAP embeddings and cleaning columns"""
        self.logger.info("Transforming posts with UMAP embeddings")
        
        # Convert to DataFrame and add timestamp
        posts_df = pd.DataFrame(posts)
        posts_df['collected_at'] = pd.Timestamp.now(tz='UTC')
        
        # Convert timestamp columns to proper datetime
        if 'created_at' in posts_df.columns:
            posts_df['created_at'] = pd.to_datetime(posts_df['created_at'], utc=True)
        
        # Generate UMAP embeddings using saved parametric model
        try:
            embedded_posts = encoder.run(
                posts_df.to_dict('records'), 
                use_parametric=True,
                umap_model_path='hf://notMuhammad/atproto-topic-umap',
                skip_embedding=False,
                use_pca=False
            )
            
            embedded_df = pd.DataFrame(embedded_posts)
            
            if 'UMAP1' not in embedded_df.columns:
                self.logger.error("UMAP embedding failed - no UMAP coordinates found")
                # Keep only essential columns without UMAP
                essential_cols_no_umap = [col for col in self.essential_columns 
                                        if col in posts_df.columns and not col.startswith('UMAP')]
                return posts_df[essential_cols_no_umap]
            
            self.logger.info("Successfully generated UMAP embeddings using parametric model")
            
            # Keep only essential columns including UMAP coordinates
            available_cols = [col for col in self.essential_columns if col in embedded_df.columns]
            return embedded_df[available_cols]
            
        except Exception as e:
            self.logger.error(f"Error generating UMAP embeddings: {str(e)}")
            # Keep only essential columns without UMAP
            essential_cols_no_umap = [col for col in self.essential_columns 
                                    if col in posts_df.columns and not col.startswith('UMAP')]
            return posts_df[essential_cols_no_umap]
    
    def load_posts(self, posts_df):
        """Load posts to BigQuery"""
        self.logger.info("Loading posts to BigQuery")
        
        self.bigquery_client.append(
            posts_df,
            self.dataset_id,
            self.posts_table,
            create_if_not_exists=True
        )
        
        self.logger.info(f"Successfully loaded {len(posts_df)} posts to BigQuery")
    
    def should_calculate_density(self):
        """Check if density should be calculated based on timing"""
        try:
            query = f"""
            SELECT MAX(calculated_at) as last_calculation
            FROM `{self.project_id}.{self.dataset_id}.{self.density_table}`
            """
            
            result = self.bigquery_client.execute_query(query)
            
            if len(result) == 0 or pd.isna(result.iloc[0]['last_calculation']):
                self.logger.info("No previous density calculation found - will calculate")
                return True
            
            last_calculation = pd.to_datetime(result.iloc[0]['last_calculation'], utc=True)
            time_since_last = pd.Timestamp.now(tz='UTC') - last_calculation
            
            should_calculate = time_since_last > timedelta(minutes=self.density_interval_minutes)
            
            self.logger.info(f"Last density calculation: {last_calculation}, "
                           f"Time since: {time_since_last}, "
                           f"Should calculate: {should_calculate}")
            
            return should_calculate
            
        except Exception as e:
            self.logger.warning(f"Error checking last density calculation, will calculate: {e}")
            return True

    def should_export_data(self):
        """Check if data export should happen based on timing (hourly)"""
        try:
            # Check if last_update.json exists and when it was created
            import os
            if not os.path.exists('data/last_update.json'):
                self.logger.info("No previous export found - will export")
                return True
            
            with open('data/last_update.json', 'r') as f:
                update_info = json.load(f)
            
            last_export = pd.to_datetime(update_info['last_update'])
            time_since_last = pd.Timestamp.now() - last_export
            
            should_export = time_since_last > timedelta(minutes=self.export_interval_minutes)
            
            self.logger.info(f"Last export: {last_export}, "
                           f"Time since: {time_since_last}, "
                           f"Should export: {should_export}")
            
            return should_export
            
        except Exception as e:
            self.logger.warning(f"Error checking last export, will export: {e}")
            return True
    
    def calculate_and_load_density(self):
        """Calculate density from recent posts and load to BigQuery"""
        self.logger.info("Calculating density from recent posts")
        
        # Get recent posts with UMAP coordinates (last 30 minutes for real-time topic evolution)
        recent_posts_query = f"""
        SELECT uri, text, author, like_count, reply_count, repost_count, created_at, collected_at,
               UMAP1, UMAP2, UMAP3, UMAP4, UMAP5
        FROM `{self.project_id}.{self.dataset_id}.{self.posts_table}`
        WHERE TIMESTAMP(collected_at) >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 MINUTE)
          AND UMAP1 IS NOT NULL AND UMAP2 IS NOT NULL
        ORDER BY collected_at DESC
        LIMIT 1000
        """
        
        recent_posts_df = self.bigquery_client.execute_query(recent_posts_query)
        
        if len(recent_posts_df) < 10:
            self.logger.warning(f"Not enough recent posts for density calculation: {len(recent_posts_df)}")
            return False
        
        # Convert UMAP coordinates to numeric (BigQuery returns them as strings)
        umap_cols = ['UMAP1', 'UMAP2', 'UMAP3', 'UMAP4', 'UMAP5']
        for col in umap_cols:
            if col in recent_posts_df.columns:
                recent_posts_df[col] = pd.to_numeric(recent_posts_df[col], errors='coerce')
        
        self.logger.info(f"Processing {len(recent_posts_df)} posts for density calculation")
        
        # Calculate density using existing UMAP coordinates
        density_result = density.model(
            recent_posts_df,
            x_col='UMAP1',
            y_col='UMAP2',
            base_resolution=50,  # Lower resolution for cloud function
            sigma=1.5,
            verbose=True
        )
        
        if density_result is None:
            self.logger.warning("Density calculation returned None")
            return False
        
        # Create density DataFrame for storage
        density_df = pd.DataFrame({
            'x': density_result['x_flat'],
            'y': density_result['y_flat'],
            'density': density_result['density_flat'],
            'calculated_at': pd.Timestamp.now(tz='UTC'),
            'posts_count': len(recent_posts_df)
        })
        
        # Ensure calculated_at is proper timestamp
        density_df['calculated_at'] = pd.to_datetime(density_df['calculated_at'], utc=True)
        
        # Save density to BigQuery
        self.logger.info("Loading density data to BigQuery")
        self.bigquery_client.append(
            density_df,
            self.dataset_id,
            self.density_table,
            create_if_not_exists=True
        )
        
        self.logger.info(f"Successfully loaded {len(density_df)} density points to BigQuery")
        
        return True
    
    def export_visualization_data(self):
        """Export data for GitHub Pages visualization"""
        try:
            self.logger.info("Exporting visualization data")
            
            # Export density data (last 24 hours)
            density_query = f"""
            SELECT x, y, density, calculated_at, posts_count
            FROM `{self.project_id}.{self.dataset_id}.{self.density_table}`
            WHERE TIMESTAMP(calculated_at) >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
            ORDER BY calculated_at DESC
            """
            
            density_df = self.bigquery_client.execute_query(density_query)
            
            # Ensure data directory exists
            import os
            os.makedirs('data', exist_ok=True)
            
            density_df.to_json('data/density_data.json', orient='records', date_format='iso')
            
            # Export recent posts with UMAP coordinates
            posts_query = f"""
            SELECT uri, text, author, like_count, reply_count, repost_count, 
                   UMAP1, UMAP2, created_at
            FROM `{self.project_id}.{self.dataset_id}.{self.posts_table}`
            WHERE UMAP1 IS NOT NULL AND UMAP2 IS NOT NULL
            AND SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ', created_at) >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
            ORDER BY created_at DESC
            LIMIT 5000
            """
            
            posts_df = self.bigquery_client.execute_query(posts_query)
            posts_df.to_json('data/posts.json', orient='records', date_format='iso')
            
            # Create update timestamp file
            update_info = {
                "last_update": datetime.now().isoformat(),
                "density_points": len(density_df),
                "posts_count": len(posts_df),
                "time_slices": len(density_df['calculated_at'].unique()) if len(density_df) > 0 else 0
            }
            
            with open('data/last_update.json', 'w') as f:
                json.dump(update_info, f, indent=2)
                
            self.logger.info(f"Exported {len(density_df)} density points and {len(posts_df)} posts")
            
            # Commit and push to GitHub
            self.commit_to_github()
            
        except Exception as e:
            self.logger.error(f"Error exporting visualization data: {str(e)}")

    def commit_to_github(self):
        """Commit updated JSON files to GitHub"""
        try:
            import subprocess
            
            # Configure git (only needed once, but safe to repeat)
            subprocess.run(['git', 'config', 'user.name', 'Railway ETL Bot'])
            subprocess.run(['git', 'config', 'user.email', 'etl@railway.app'])
            
            # Add the JSON files
            subprocess.run(['git', 'add', 'data/density_data.json', 'data/posts.json', 'data/last_update.json'])
            
            # Commit with timestamp
            commit_msg = f"Update visualization data - {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
            result = subprocess.run(['git', 'commit', '-m', commit_msg], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Push to GitHub
                subprocess.run(['git', 'push', 'origin', 'main'])
                self.logger.info("Successfully pushed updated data to GitHub")
            else:
                self.logger.info("No changes to commit")
                
        except Exception as e:
            self.logger.error(f"Error committing to GitHub: {str(e)}")
    
    def run_etl(self):
        """Run the complete ETL pipeline"""
        try:
            self.logger.info("Starting AT Proto synoptic chart ETL pipeline")
            
            # Initialize clients
            self.initialize_clients()
            
            # Extract posts
            posts = self.extract_posts()
            if posts is None:
                return {"status": "success", "message": "No new posts to process"}
            
            # Transform posts
            posts_df = self.transform_posts(posts)
            
            # Load posts
            self.load_posts(posts_df)
            
            # Check if density calculation is needed
            density_calculated = False
            if self.should_calculate_density():
                density_calculated = self.calculate_and_load_density()
            else:
                self.logger.info("Skipping density calculation - not time yet")
            
            # Check if data export is needed (independent of density - runs hourly)
            data_exported = False
            if self.should_export_data():
                self.export_visualization_data()
                data_exported = True
            else:
                self.logger.info("Skipping data export - not time yet")
            
            # Return success response
            return {
                "status": "success",
                "posts_collected": len(posts_df),
                "density_calculated": density_calculated,
                "data_exported": data_exported,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in ETL pipeline: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# Cloud Function entry point
def collect_and_process_posts(request):
    """
    Cloud Function entry point for the ETL pipeline.
    Runs every 10 minutes to collect posts, calculates density every 30 minutes.
    """
    etl = ATProtoETL()
    return etl.run_etl()

# For local testing
if __name__ == "__main__":
    # Mock request object for local testing
    class MockRequest:
        pass
    
    result = collect_and_process_posts(MockRequest())
    print(json.dumps(result, indent=2))