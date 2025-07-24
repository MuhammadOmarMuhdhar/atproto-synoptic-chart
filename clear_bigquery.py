from google.cloud import bigquery
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load credentials from environment variable
credentials_json = json.loads(os.environ['BIGQUERY_CREDENTIALS_JSON'])
project_id = os.environ['BIGQUERY_PROJECT_ID']
dataset_id = os.environ['BIGQUERY_DATASET_ID']

# Initialize BigQuery client
client = bigquery.Client.from_service_account_info(credentials_json, project=project_id)

# Clear posts table
posts_table_id = f"{project_id}.{dataset_id}.posts"
try:
    query = f"DELETE FROM `{posts_table_id}` WHERE TRUE"
    job = client.query(query)
    job.result()  # Wait for completion
    print(f"✅ Cleared all data from {posts_table_id}")
except Exception as e:
    print(f"❌ Error clearing posts table: {e}")

# Clear density table  
density_table_id = f"{project_id}.{dataset_id}.density"
try:
    query = f"DELETE FROM `{density_table_id}` WHERE TRUE"
    job = client.query(query)
    job.result()  # Wait for completion
    print(f"✅ Cleared all data from {density_table_id}")
except Exception as e:
    print(f"❌ Error clearing density table: {e}")

print("🧹 BigQuery cleanup complete!")