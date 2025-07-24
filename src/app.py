from flask import Flask, request, jsonify
from etl import collect_and_process_posts
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

@app.route('/', methods=['POST', 'GET'])
def trigger_etl():
    """
    HTTP endpoint to trigger ETL pipeline
    Google Cloud Scheduler will call this endpoint every 10 minutes
    """
    try:
        logger.info("ETL pipeline triggered")
        
        # Call your existing ETL function
        result = collect_and_process_posts(None)
        
        logger.info(f"ETL completed successfully: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"ETL pipeline failed: {str(e)}")
        return jsonify({"error": str(e), "status": "failed"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for Google Cloud Run
    This endpoint tells Google Cloud Run that your service is healthy
    """
    return jsonify({"status": "healthy", "service": "atproto-etl"})

if __name__ == '__main__':
    # Get port from environment (Cloud Run sets this)
    port = int(os.environ.get('PORT', 8080))
    
    logger.info(f"Starting Flask app on port {port}")
    
    # Run the Flask app
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=port,       # Use the port Cloud Run provides
        debug=False      # Disable debug mode in production
    )