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

log_info "Deleting stack..."

aws cloudformation delete-stack \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION"

log_info "Waiting for deletion..."

aws cloudformation wait stack-delete-complete \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION"

log_info "Stack deleted successfully."