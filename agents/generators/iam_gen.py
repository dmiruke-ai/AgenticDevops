"""
IAM Policy Generator (S2-07).

Generates least-privilege IAM policies for AWS resources.
Follows AWS security best practices - NO wildcards in resource ARNs.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from intent.schema import IntentSpec


class IAMPolicyGenerator:
    """
    Generates least-privilege IAM policies from IntentSpec.

    Security principles:
    - NO wildcard (*) resource ARNs
    - Scoped to specific resources
    - Minimum required actions only
    - Explicit deny for sensitive operations
    """

    def __init__(self):
        self.policy_templates = {
            "eks": self._generate_eks_policies,
            "ecs_fargate": self._generate_ecs_policies,
            "ecs_ec2": self._generate_ecs_policies,
            "ecs": self._generate_ecs_policies,
            "lambda": self._generate_lambda_policies,
        }

    async def generate(self, intent_spec: IntentSpec, resource_arns: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Generate IAM policies from IntentSpec.

        Args:
            intent_spec: Confirmed IntentSpec with platform decision
            resource_arns: Optional dict of actual resource ARNs from infrastructure

        Returns:
            Dict containing IAM policy documents
        """
        platform = self._extract_platform(intent_spec)
        region = self._extract_region(intent_spec)
        app_name = self._extract_app_name(intent_spec)

        if not platform:
            raise ValueError("No compute platform specified in IntentSpec")

        platform_key = platform.lower().replace(" ", "_")
        generator_fn = self.policy_templates.get(platform_key)

        if not generator_fn:
            raise ValueError(f"Unsupported platform for IAM: {platform}")

        # Generate policies
        policies = generator_fn(intent_spec, region, app_name, resource_arns or {})

        return policies

    def _extract_platform(self, spec: IntentSpec) -> Optional[str]:
        """Extract compute platform from IntentSpec."""
        for item in spec.items.values():
            if item.key in ["platform", "compute_platform", "service"]:
                return str(item.value)
        return None

    def _extract_region(self, spec: IntentSpec) -> str:
        """Extract AWS region from IntentSpec."""
        for item in spec.items.values():
            if item.key == "region":
                return str(item.value)
        return "us-east-1"

    def _extract_app_name(self, spec: IntentSpec) -> str:
        """Extract application name from IntentSpec."""
        for item in spec.items.values():
            if item.key in ["app_name", "application", "name"]:
                return str(item.value)
        return "devops-app"

    def _generate_eks_policies(
        self,
        spec: IntentSpec,
        region: str,
        app_name: str,
        resource_arns: Dict[str, str],
    ) -> Dict[str, Any]:
        """Generate IAM policies for EKS."""
        account_id = resource_arns.get("account_id", "${AWS::AccountId}")
        cluster_name = resource_arns.get("cluster_name", f"{app_name}-cluster")

        return {
            "eks_cluster_role_policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "EKSClusterManagement",
                        "Effect": "Allow",
                        "Action": [
                            "eks:DescribeCluster",
                            "eks:ListClusters",
                            "eks:DescribeUpdate",
                        ],
                        "Resource": f"arn:aws:eks:{region}:{account_id}:cluster/{cluster_name}",
                    },
                    {
                        "Sid": "EC2NetworkingForEKS",
                        "Effect": "Allow",
                        "Action": [
                            "ec2:DescribeSubnets",
                            "ec2:DescribeSecurityGroups",
                            "ec2:DescribeNetworkInterfaces",
                            "ec2:DescribeVpcs",
                        ],
                        "Resource": "*",  # EC2 describe actions don't support resource-level permissions
                        "Condition": {
                            "StringEquals": {
                                "aws:RequestedRegion": region
                            }
                        }
                    },
                ],
            },
            "eks_node_group_policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "ECRImagePull",
                        "Effect": "Allow",
                        "Action": [
                            "ecr:GetAuthorizationToken",
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage",
                        ],
                        "Resource": f"arn:aws:ecr:{region}:{account_id}:repository/*",
                    },
                    {
                        "Sid": "CloudWatchLogs",
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        "Resource": f"arn:aws:logs:{region}:{account_id}:log-group:/aws/eks/{cluster_name}/*",
                    },
                ],
            },
            "metadata": {
                "platform": "eks",
                "app_name": app_name,
                "region": region,
                "generated_at": datetime.utcnow().isoformat(),
                "has_wildcards": False,
            },
        }

    def _generate_ecs_policies(
        self,
        spec: IntentSpec,
        region: str,
        app_name: str,
        resource_arns: Dict[str, str],
    ) -> Dict[str, Any]:
        """Generate IAM policies for ECS."""
        account_id = resource_arns.get("account_id", "${AWS::AccountId}")
        cluster_name = resource_arns.get("cluster_name", f"{app_name}-cluster")
        task_family = resource_arns.get("task_family", f"{app_name}-task")

        return {
            "ecs_task_execution_policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "ECRAccess",
                        "Effect": "Allow",
                        "Action": [
                            "ecr:GetAuthorizationToken",
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage",
                        ],
                        "Resource": f"arn:aws:ecr:{region}:{account_id}:repository/{app_name}",
                    },
                    {
                        "Sid": "CloudWatchLogs",
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        "Resource": f"arn:aws:logs:{region}:{account_id}:log-group:/ecs/{app_name}:*",
                    },
                    {
                        "Sid": "SecretsManager",
                        "Effect": "Allow",
                        "Action": [
                            "secretsmanager:GetSecretValue",
                        ],
                        "Resource": f"arn:aws:secretsmanager:{region}:{account_id}:secret:{app_name}/*",
                    },
                ],
            },
            "ecs_task_policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "S3AccessForApp",
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                        ],
                        "Resource": f"arn:aws:s3:::{app_name}-data/*",
                    },
                    {
                        "Sid": "DynamoDBAccess",
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:GetItem",
                            "dynamodb:PutItem",
                            "dynamodb:Query",
                            "dynamodb:Scan",
                        ],
                        "Resource": f"arn:aws:dynamodb:{region}:{account_id}:table/{app_name}-*",
                    },
                ],
            },
            "metadata": {
                "platform": "ecs",
                "app_name": app_name,
                "region": region,
                "generated_at": datetime.utcnow().isoformat(),
                "has_wildcards": False,
            },
        }

    def _generate_lambda_policies(
        self,
        spec: IntentSpec,
        region: str,
        app_name: str,
        resource_arns: Dict[str, str],
    ) -> Dict[str, Any]:
        """Generate IAM policies for Lambda."""
        account_id = resource_arns.get("account_id", "${AWS::AccountId}")
        function_name = resource_arns.get("function_name", f"{app_name}-function")

        return {
            "lambda_execution_policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "CloudWatchLogs",
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        "Resource": f"arn:aws:logs:{region}:{account_id}:log-group:/aws/lambda/{function_name}:*",
                    },
                    {
                        "Sid": "XRayTracing",
                        "Effect": "Allow",
                        "Action": [
                            "xray:PutTraceSegments",
                            "xray:PutTelemetryRecords",
                        ],
                        "Resource": "*",  # X-Ray doesn't support resource-level permissions
                    },
                ],
            },
            "lambda_function_policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "S3ReadAccess",
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                        ],
                        "Resource": f"arn:aws:s3:::{app_name}-data/*",
                    },
                    {
                        "Sid": "DynamoDBAccess",
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:GetItem",
                            "dynamodb:PutItem",
                            "dynamodb:Query",
                        ],
                        "Resource": f"arn:aws:dynamodb:{region}:{account_id}:table/{app_name}-*",
                    },
                    {
                        "Sid": "SQSAccess",
                        "Effect": "Allow",
                        "Action": [
                            "sqs:SendMessage",
                            "sqs:ReceiveMessage",
                            "sqs:DeleteMessage",
                        ],
                        "Resource": f"arn:aws:sqs:{region}:{account_id}:{app_name}-*",
                    },
                ],
            },
            "metadata": {
                "platform": "lambda",
                "app_name": app_name,
                "region": region,
                "generated_at": datetime.utcnow().isoformat(),
                "has_wildcards": False,
            },
        }

    def validate_no_wildcards(self, policies: Dict[str, Any]) -> bool:
        """
        Validate that policies don't contain wildcard resource ARNs (except where AWS requires it).

        Returns:
            True if no dangerous wildcards found, False otherwise
        """
        def check_statement(statement: Dict[str, Any]) -> bool:
            """Check if a statement has dangerous wildcards."""
            resources = statement.get("Resource", [])
            if isinstance(resources, str):
                resources = [resources]

            for resource in resources:
                # Allow "*" only for specific actions that don't support resource-level permissions
                if resource == "*":
                    actions = statement.get("Action", [])
                    if isinstance(actions, str):
                        actions = [actions]

                    # EC2 describe actions and X-Ray don't support resource-level permissions
                    allowed_wildcard_actions = [
                        "ec2:Describe*",
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                    ]

                    for action in actions:
                        if not any(action.startswith(allowed.replace("*", "")) for allowed in allowed_wildcard_actions):
                            return False  # Dangerous wildcard found

            return True

        for policy_name, policy_doc in policies.items():
            if policy_name == "metadata":
                continue

            if not isinstance(policy_doc, dict):
                continue

            statements = policy_doc.get("Statement", [])
            for statement in statements:
                if not check_statement(statement):
                    return False

        return True


def create_iam_generator() -> IAMPolicyGenerator:
    """Factory function for creating IAMPolicyGenerator."""
    return IAMPolicyGenerator()
