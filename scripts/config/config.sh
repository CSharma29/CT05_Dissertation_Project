# config/config.sh

##############################################
# Global Configuration
##############################################
export AWS_REGION="${AWS_REGION:-ap-southeast-1}"
export ARTIFACT_BUCKET="${ARTIFACT_BUCKET:-ct05-cloudformation-artifacts-singapore}"

# S3_PREFIX must come after AWS_REGION and ARTIFACT_BUCKET
export S3_PREFIX="${S3_PREFIX:-https://${ARTIFACT_BUCKET}.s3.${AWS_REGION}.amazonaws.com}"

export STACK_NAME="${STACK_NAME:-CT05-ChiragDissertation-01}"
export TEMPLATE_FILE="${TEMPLATE_FILE:-cloudformation/main.yaml}"
export PACKAGED_TEMPLATE="${PACKAGED_TEMPLATE:-packaged.yaml}"

##############################################
# Lambda Configuration
##############################################
export HANDLE_CONVERSATION_LAMBDA="${HANDLE_CONVERSATION_LAMBDA:-lambda/handle_conversation}"
export ORCHESTRATE_CONVERSATION_LAMBDA="${ORCHESTRATE_CONVERSATION_LAMBDA:-lambda/orchestrate_conversation}"