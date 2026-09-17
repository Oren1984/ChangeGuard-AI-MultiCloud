from enum import StrEnum


class ChangeType(StrEnum):
    APPLICATION_CODE = "application_code"
    TERRAFORM_PLAN = "terraform_plan"
    HELM_K8S_CONFIG = "helm_k8s_config"
    DB_MIGRATION = "db_migration"
    IAM_POLICY = "iam_policy"
    API_CONTRACT = "api_contract"
    CONFIGURATION = "configuration"
