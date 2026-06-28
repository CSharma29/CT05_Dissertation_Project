#!/bin/bash

set -Eeuo pipefail

# Source shared config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config/config.sh"

##############################################
# Logging Functions
##############################################

timestamp() {
    date +"%Y-%m-%d %H:%M:%S"
}

log_info() {
    echo "[$(timestamp)] [INFO ] $1"
}

log_error() {
    echo "[$(timestamp)] [ERROR] $1"
}

##############################################
# Check Artifact Bucket
##############################################

log_info "Checking if artifact bucket exists..."

if aws s3api head-bucket \
    --bucket "$ARTIFACT_BUCKET" 2>/dev/null; then

    log_info "Artifact bucket '$ARTIFACT_BUCKET' found."

else

    log_info "Artifact bucket does not exist."
    log_info "Creating bucket '$ARTIFACT_BUCKET'..."

    if [ "$AWS_REGION" = "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "$ARTIFACT_BUCKET"
    else
        aws s3api create-bucket \
            --bucket "$ARTIFACT_BUCKET" \
            --region "$AWS_REGION" \
            --create-bucket-configuration \
            LocationConstraint="$AWS_REGION"
    fi

    log_info "Bucket created successfully."

fi
##############################################
# Build Lambda Deployment Packages
##############################################

log_info "Building Lambda deployment packages..."

mkdir -p build

##############################################
# Handle Conversation Lambda
##############################################

log_info "Packaging Handle Conversation Lambda..."

(
    cd lambda/handle_conversation

    zip -rq ../../build/handle_conversation.zip .
)

##############################################
# Orchestrate Conversation Lambda
##############################################

log_info "Packaging Orchestrate Conversation Lambda..."

(
    cd lambda/orchestrate_conversation

    zip -rq ../../build/orchestrate_conversation.zip .
)

log_info "Lambda deployment packages created."

##############################################
# Upload Lambda Packages
##############################################

log_info "Uploading Lambda deployment packages..."

aws s3 cp \
    build/handle_conversation.zip \
    s3://"$ARTIFACT_BUCKET"/handle_conversation.zip \
    --region "$AWS_REGION"

aws s3 cp \
    build/orchestrate_conversation.zip \
    s3://"$ARTIFACT_BUCKET"/orchestrate_conversation.zip \
    --region "$AWS_REGION"

log_info "Lambda packages uploaded successfully."

##############################################
# Package CloudFormation Templates
##############################################

log_info "Packaging CloudFormation templates..."

aws cloudformation package \
    --template-file "$TEMPLATE_FILE" \
    --s3-bucket "$ARTIFACT_BUCKET" \
    --output-template-file "$PACKAGED_TEMPLATE" \
    --region "$AWS_REGION"

##############################################
# Verify Output
##############################################

if [ -f "$PACKAGED_TEMPLATE" ]; then
    log_info "Packaging completed successfully."
    log_info "Packaged template created:"
    log_info "$(pwd)/$PACKAGED_TEMPLATE"
else
    log_error "packaged.yaml was not created."
    exit 1
fi