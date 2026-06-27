log_info "Validating CloudFormation template..."

AWS_REGION="ap-south-1"

aws cloudformation validate-template \
    --template-body file://cloudformation/main.yaml \
    --region "$AWS_REGION"

log_info "Validation successful."