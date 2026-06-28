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
# Error Handler
##############################################
handle_error() {
  log_error "Deployment failed."
  echo ""
  # FIX 1: Only fetch stack events if the stack actually exists
  if aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" 2>/dev/null; then
    log_info "Fetching latest CloudFormation events..."
    aws cloudformation describe-stack-events \
      --stack-name "$STACK_NAME" \
      --region "$AWS_REGION" \
      --max-items 10 \
      --output table || true
  else
    log_error "Stack '$STACK_NAME' does not exist yet — no events to fetch."
  fi
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
# Deploy Stack - Create or Update
##############################################
# FIX 2: Handle both first run (create) and subsequent runs (update)
if aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" 2>/dev/null; then

  log_info "Stack '$STACK_NAME' exists — updating..."
  aws cloudformation update-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://"$PACKAGED_TEMPLATE" \
    --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
    --region "$AWS_REGION" \
    --parameters ParameterKey=ArtiFactBucketName,ParameterValue="$ARTIFACT_BUCKET"

  log_info "Waiting for update to complete..."
  aws cloudformation wait stack-update-complete \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION"

else

  log_info "Stack '$STACK_NAME' does not exist — creating..."
  aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://"$PACKAGED_TEMPLATE" \
    --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
    --disable-rollback \
    --region "$AWS_REGION" \
    --parameters ParameterKey=ArtiFactBucketName,ParameterValue="$ARTIFACT_BUCKET"

  log_info "Waiting for creation to complete..."
  aws cloudformation wait stack-create-complete \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION"

fi

##############################################
# Display Outputs
##############################################
log_info "Deployment completed successfully."
echo ""
log_info "Stack Outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs" \
  --output table

echo ""
log_info "Stack Status:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query "Stacks[0].StackStatus"