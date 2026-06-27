#!/bin/bash

set -Eeuo pipefail

##############################################
# Configuration
##############################################

AWS_REGION="ap-south-1"
STACK_NAME="CT05-ChiragDissertation-01"
PACKAGED_TEMPLATE="packaged.yaml"

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
# Error Handler
##############################################

handle_error() {

    log_error "Deployment failed."

    echo ""
    log_info "Fetching latest CloudFormation events..."

    aws cloudformation describe-stack-events \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" \
        --max-items 10 \
        --output table || true

    exit 1
}

trap handle_error ERR

##############################################
# Validate AWS Credentials
##############################################

log_info "Checking AWS credentials..."

aws sts get-caller-identity \
    --region "$AWS_REGION" > /dev/null

log_info "AWS credentials are valid."

##############################################
# Verify Packaged Template
##############################################

if [ ! -f "$PACKAGED_TEMPLATE" ]; then
    log_error "$PACKAGED_TEMPLATE not found."

    log_error "Run package.sh before deploying."

    exit 1
fi

log_info "Using packaged template: $PACKAGED_TEMPLATE"

##############################################
# Deploy Stack
##############################################

log_info "Deploying CloudFormation stack..."

aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://"$PACKAGED_TEMPLATE" \
    --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
    --disable-rollback \
    --region "$AWS_REGION"

##############################################
# Wait for Completion
##############################################

log_info "Waiting for deployment to complete..."

aws cloudformation wait stack-create-complete \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION"

##############################################
# Display Outputs
##############################################

log_info "Deployment completed successfully."

echo ""

log_info "Stack Outputs"

aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query "Stacks[0].Outputs" \
    --output table

echo ""

log_info "Stack Status"

aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query "Stacks[0].StackStatus"