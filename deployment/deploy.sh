#!/bin/bash

# AT Proto Synoptic Chart - Cloud Function Deployment Script
# This script deploys the data collection function and sets up the scheduler

set -e

# Configuration
FUNCTION_NAME="atproto-synoptic-chart"
REGION="us-central1"
PROJECT_ID="atproto-synoptic-chart"
JOB_NAME="atproto-data-collection"
SCHEDULE="*/10 * * * *"  # Every 10 minutes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying AT Proto Synoptic Chart Cloud Function${NC}"
echo "=================================================="

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if logged in to gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${YELLOW}⚠️  You are not logged in to gcloud. Logging in...${NC}"
    gcloud auth login
fi

# Set the project
echo -e "${YELLOW}📋 Setting project: ${PROJECT_ID}${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "${YELLOW}🔧 Enabling required APIs...${NC}"
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable appengine.googleapis.com

# Create App Engine app if it doesn't exist (required for Cloud Scheduler)
echo -e "${YELLOW}🏗️  Checking App Engine app...${NC}"
if ! gcloud app describe &>/dev/null; then
    echo -e "${YELLOW}Creating App Engine app in ${REGION}...${NC}"
    gcloud app create --region=${REGION}
fi

# Check if .env file exists
if [ ! -f "../.env" ]; then
    echo -e "${RED}❌ .env file not found in parent directory. Please create it first.${NC}"
    exit 1
fi

# Read environment variables from .env file
echo -e "${YELLOW}📋 Reading environment variables from .env file...${NC}"
export $(grep -v '^#' ../.env | xargs)

# Deploy the Cloud Function
echo -e "${YELLOW}📦 Deploying Cloud Function: ${FUNCTION_NAME}${NC}"
gcloud functions deploy ${FUNCTION_NAME} \
    --gen2 \
    --runtime=python311 \
    --region=${REGION} \
    --source=. \
    --entry-point=collect_and_process_posts \
    --trigger-http \
    --allow-unauthenticated \
    --memory=1GB \
    --timeout=540s \
    --set-env-vars="BLUESKY_USERNAME=${BLUESKY_USERNAME},BLUESKY_PASSWORD=${BLUESKY_PASSWORD},BIGQUERY_PROJECT_ID=${BIGQUERY_PROJECT_ID},BIGQUERY_DATASET_ID=${BIGQUERY_DATASET_ID},BIGQUERY_TABLE_ID_POSTS=${BIGQUERY_TABLE_ID_POSTS},BIGQUERY_TABLE_ID_DENSITY=${BIGQUERY_TABLE_ID_DENSITY},BIGQUERY_CREDENTIALS_JSON=${BIGQUERY_CREDENTIALS_JSON}"

# Get the Cloud Function URL
FUNCTION_URL=$(gcloud functions describe ${FUNCTION_NAME} --region=${REGION} --format="value(serviceConfig.uri)")
echo -e "${GREEN}✅ Cloud Function deployed successfully!${NC}"
echo -e "${GREEN}   URL: ${FUNCTION_URL}${NC}"

# Create or update Cloud Scheduler job
echo -e "${YELLOW}⏰ Setting up Cloud Scheduler job: ${JOB_NAME}${NC}"

# Check if job already exists
if gcloud scheduler jobs describe ${JOB_NAME} --location=${REGION} &>/dev/null; then
    echo -e "${YELLOW}📝 Updating existing scheduler job...${NC}"
    gcloud scheduler jobs update http ${JOB_NAME} \
        --location=${REGION} \
        --schedule="${SCHEDULE}" \
        --uri="${FUNCTION_URL}" \
        --http-method=POST \
        --headers="Content-Type=application/json" \
        --message-body='{}' \
        --time-zone="UTC"
else
    echo -e "${YELLOW}🆕 Creating new scheduler job...${NC}"
    gcloud scheduler jobs create http ${JOB_NAME} \
        --location=${REGION} \
        --schedule="${SCHEDULE}" \
        --uri="${FUNCTION_URL}" \
        --http-method=POST \
        --headers="Content-Type=application/json" \
        --message-body='{}' \
        --time-zone="UTC" \
        --description="Collect Bluesky posts every 10 minutes for AT Proto synoptic chart"
fi

echo -e "${GREEN}✅ Cloud Scheduler job configured successfully!${NC}"
echo -e "${GREEN}   Schedule: ${SCHEDULE} (every 10 minutes)${NC}"
echo -e "${GREEN}   Timezone: UTC${NC}"

# Test the function (optional)
echo -e "${YELLOW}🧪 Testing the deployed function...${NC}"
curl -X POST "${FUNCTION_URL}" \
    -H "Content-Type: application/json" \
    -d '{}' | jq '.' || echo -e "${YELLOW}(jq not available, showing raw response)${NC}"

echo ""
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo "=================================================="
echo -e "${GREEN}📊 Your AT Proto Synoptic Chart is now live!${NC}"
echo ""
echo -e "${GREEN}📋 Summary:${NC}"
echo -e "   Cloud Function: ${FUNCTION_NAME}"
echo -e "   Region: ${REGION}"
echo -e "   Schedule: Every 10 minutes"
echo -e "   Data Collection: Bluesky posts → BigQuery"
echo -e "   Density Calculation: Every 30 minutes"
echo ""
echo -e "${GREEN}🔍 Monitoring:${NC}"
echo -e "   Logs: gcloud functions logs read ${FUNCTION_NAME} --region=${REGION}"
echo -e "   Jobs: gcloud scheduler jobs list --location=${REGION}"
echo -e "   Function URL: ${FUNCTION_URL}"
echo ""
echo -e "${YELLOW}⚠️  Note: The first few runs may take longer as dependencies are cached.${NC}"