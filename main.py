#!/usr/bin/env python3
"""
Simple ETL runner for Railway deployment
Runs the AT Proto synoptic chart ETL pipeline
"""

import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.append(str(Path(__file__).parent))

from ETL.etl import collect_and_process_posts

if __name__ == "__main__":
    print("Starting AT Proto ETL pipeline...")
    
    try:
        # Run the ETL pipeline
        result = collect_and_process_posts(None)
        
        print(f"ETL completed: {result}")
        
        # Exit with appropriate code
        if result.get("status") == "error":
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"ETL failed: {e}")
        sys.exit(1)