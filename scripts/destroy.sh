log_info "Deleting stack..."

aws cloudformation delete-stack \
    --stack-name "$STACK_NAME" \
    --region "$REGION"

log_info "Waiting for deletion..."

aws cloudformation wait stack-delete-complete \
    --stack-name "$STACK_NAME" \
    --region "$REGION"

log_info "Stack deleted successfully."