log_info "Validating CloudFormation template..."
# Source shared config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config/config.sh"

aws cloudformation validate-template \
    --template-body file://cloudformation/main.yaml \
    --region "$AWS_REGION"

log_info "Validation successful."