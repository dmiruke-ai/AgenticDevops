"""
Terraform Infrastructure Generator (S2-06).

Generates valid Terraform HCL for EKS, ECS Fargate, ECS EC2, and Lambda platforms.
Uses template-based generation with IntentSpec-driven parameter substitution.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from intent.schema import IntentSpec


class TerraformGenerator:
    """
    Generates Terraform HCL files from IntentSpec.

    Supports platforms:
    - EKS (Elastic Kubernetes Service)
    - ECS Fargate (serverless containers)
    - ECS EC2 (container instances)
    - Lambda (serverless functions)
    """

    def __init__(self):
        self.templates = {
            "eks": self._generate_eks,
            "ecs_fargate": self._generate_ecs_fargate,
            "ecs_ec2": self._generate_ecs_ec2,
            "ecs": self._generate_ecs_fargate,  # Default to Fargate
            "lambda": self._generate_lambda,
        }

    async def generate(self, intent_spec: IntentSpec) -> Dict[str, str]:
        """
        Generate Terraform files from IntentSpec.

        Args:
            intent_spec: Confirmed IntentSpec with platform decision

        Returns:
            Dict mapping filename -> HCL content
            Example: {
                "main.tf": "...",
                "variables.tf": "...",
                "outputs.tf": "...",
            }
        """
        # Extract platform from IntentSpec
        platform = self._extract_platform(intent_spec)
        region = self._extract_region(intent_spec)
        app_name = self._extract_app_name(intent_spec)

        if not platform:
            raise ValueError("No compute platform specified in IntentSpec")

        # Normalize platform name
        platform_key = platform.lower().replace(" ", "_")

        generator_fn = self.templates.get(platform_key)
        if not generator_fn:
            raise ValueError(f"Unsupported platform: {platform}")

        # Generate main infrastructure
        main_tf = generator_fn(intent_spec, region, app_name)

        # Generate common files
        variables_tf = self._generate_variables(intent_spec, region, app_name)
        outputs_tf = self._generate_outputs(platform_key, app_name)
        provider_tf = self._generate_provider(region)

        return {
            "main.tf": main_tf,
            "variables.tf": variables_tf,
            "outputs.tf": outputs_tf,
            "provider.tf": provider_tf,
        }

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
        return "us-east-1"  # Default

    def _extract_app_name(self, spec: IntentSpec) -> str:
        """Extract application name from IntentSpec."""
        for item in spec.items.values():
            if item.key in ["app_name", "application", "name"]:
                return str(item.value)
        return "devops-app"  # Default

    def _generate_provider(self, region: str) -> str:
        """Generate provider.tf."""
        return f'''terraform {{
  required_version = ">= 1.0"

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = var.aws_region
}}
'''

    def _generate_variables(self, spec: IntentSpec, region: str, app_name: str) -> str:
        """Generate variables.tf."""
        return f'''variable "aws_region" {{
  description = "AWS region for resources"
  type        = string
  default     = "{region}"
}}

variable "app_name" {{
  description = "Application name"
  type        = string
  default     = "{app_name}"
}}

variable "environment" {{
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}}

variable "tags" {{
  description = "Common resource tags"
  type        = map(string)
  default = {{
    ManagedBy   = "AgenticDevOps"
    GeneratedAt = "{datetime.utcnow().isoformat()}"
  }}
}}
'''

    def _generate_outputs(self, platform: str, app_name: str) -> str:
        """Generate outputs.tf based on platform."""
        if platform == "eks":
            return f'''output "cluster_endpoint" {{
  description = "EKS cluster endpoint"
  value       = aws_eks_cluster.{app_name.replace("-", "_")}.endpoint
}}

output "cluster_name" {{
  description = "EKS cluster name"
  value       = aws_eks_cluster.{app_name.replace("-", "_")}.name
}}

output "cluster_security_group_id" {{
  description = "Security group ID attached to the EKS cluster"
  value       = aws_eks_cluster.{app_name.replace("-", "_")}.vpc_config[0].cluster_security_group_id
}}
'''
        elif "ecs" in platform:
            return f'''output "cluster_name" {{
  description = "ECS cluster name"
  value       = aws_ecs_cluster.{app_name.replace("-", "_")}.name
}}

output "service_name" {{
  description = "ECS service name"
  value       = aws_ecs_service.{app_name.replace("-", "_")}.name
}}

output "load_balancer_dns" {{
  description = "Application Load Balancer DNS name"
  value       = aws_lb.{app_name.replace("-", "_")}.dns_name
}}
'''
        elif platform == "lambda":
            return f'''output "function_name" {{
  description = "Lambda function name"
  value       = aws_lambda_function.{app_name.replace("-", "_")}.function_name
}}

output "function_arn" {{
  description = "Lambda function ARN"
  value       = aws_lambda_function.{app_name.replace("-", "_")}.arn
}}

output "invoke_url" {{
  description = "API Gateway invoke URL"
  value       = aws_apigatewayv2_api.{app_name.replace("-", "_")}.api_endpoint
}}
'''
        else:
            return '# No outputs defined for this platform\n'

    def _generate_eks(self, spec: IntentSpec, region: str, app_name: str) -> str:
        """Generate EKS cluster infrastructure."""
        cluster_name = app_name.replace("-", "_")

        return f'''# EKS Cluster
resource "aws_eks_cluster" "{cluster_name}" {{
  name     = "${{var.app_name}}-cluster"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.28"

  vpc_config {{
    subnet_ids              = aws_subnet.private[*].id
    endpoint_private_access = true
    endpoint_public_access  = true
  }}

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
  ]

  tags = var.tags
}}

# EKS Node Group
resource "aws_eks_node_group" "{cluster_name}_nodes" {{
  cluster_name    = aws_eks_cluster.{cluster_name}.name
  node_group_name = "${{var.app_name}}-nodes"
  node_role_arn   = aws_iam_role.eks_node_group.arn
  subnet_ids      = aws_subnet.private[*].id

  scaling_config {{
    desired_size = 2
    max_size     = 4
    min_size     = 1
  }}

  instance_types = ["t3.medium"]

  depends_on = [
    aws_iam_role_policy_attachment.eks_node_group_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_registry_policy,
  ]]

  tags = var.tags
}}

# VPC for EKS
resource "aws_vpc" "{cluster_name}_vpc" {{
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-vpc"
  }})
}}

# Private Subnets
resource "aws_subnet" "private" {{
  count             = 2
  vpc_id            = aws_vpc.{cluster_name}_vpc.id
  cidr_block        = cidrsubnet(aws_vpc.{cluster_name}_vpc.cidr_block, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-private-${{count.index + 1}}"
    "kubernetes.io/role/internal-elb" = "1"
  }})
}}

# Public Subnets
resource "aws_subnet" "public" {{
  count                   = 2
  vpc_id                  = aws_vpc.{cluster_name}_vpc.id
  cidr_block              = cidrsubnet(aws_vpc.{cluster_name}_vpc.cidr_block, 8, count.index + 2)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-public-${{count.index + 1}}"
    "kubernetes.io/role/elb" = "1"
  }})
}}

# Internet Gateway
resource "aws_internet_gateway" "{cluster_name}_igw" {{
  vpc_id = aws_vpc.{cluster_name}_vpc.id

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-igw"
  }})
}}

# NAT Gateway
resource "aws_eip" "{cluster_name}_nat" {{
  count  = 2
  domain = "vpc"

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-nat-${{count.index + 1}}"
  }})
}}

resource "aws_nat_gateway" "{cluster_name}_nat" {{
  count         = 2
  allocation_id = aws_eip.{cluster_name}_nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-nat-${{count.index + 1}}"
  }})

  depends_on = [aws_internet_gateway.{cluster_name}_igw]
}}

# Route Tables
resource "aws_route_table" "{cluster_name}_public" {{
  vpc_id = aws_vpc.{cluster_name}_vpc.id

  route {{
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.{cluster_name}_igw.id
  }}

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-public-rt"
  }})
}}

resource "aws_route_table" "{cluster_name}_private" {{
  count  = 2
  vpc_id = aws_vpc.{cluster_name}_vpc.id

  route {{
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.{cluster_name}_nat[count.index].id
  }}

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-private-rt-${{count.index + 1}}"
  }})
}}

resource "aws_route_table_association" "{cluster_name}_public" {{
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.{cluster_name}_public.id
}}

resource "aws_route_table_association" "{cluster_name}_private" {{
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.{cluster_name}_private[count.index].id
}}

# Data source for availability zones
data "aws_availability_zones" "available" {{
  state = "available"
}}

# IAM Role for EKS Cluster
resource "aws_iam_role" "eks_cluster" {{
  name = "${{var.app_name}}-eks-cluster-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{
        Service = "eks.amazonaws.com"
      }}
      Action = "sts:AssumeRole"
    }}]
  }})

  tags = var.tags
}}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {{
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}}

# IAM Role for EKS Node Group
resource "aws_iam_role" "eks_node_group" {{
  name = "${{var.app_name}}-eks-node-group-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{
        Service = "ec2.amazonaws.com"
      }}
      Action = "sts:AssumeRole"
    }}]
  }})

  tags = var.tags
}}

resource "aws_iam_role_policy_attachment" "eks_node_group_policy" {{
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_node_group.name
}}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {{
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_node_group.name
}}

resource "aws_iam_role_policy_attachment" "eks_registry_policy" {{
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_node_group.name
}}
'''

    def _generate_ecs_fargate(self, spec: IntentSpec, region: str, app_name: str) -> str:
        """Generate ECS Fargate infrastructure."""
        resource_name = app_name.replace("-", "_")

        return f'''# ECS Cluster (Fargate)
resource "aws_ecs_cluster" "{resource_name}" {{
  name = "${{var.app_name}}-cluster"

  setting {{
    name  = "containerInsights"
    value = "enabled"
  }}

  tags = var.tags
}}

# ECS Task Definition
resource "aws_ecs_task_definition" "{resource_name}" {{
  family                   = "${{var.app_name}}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{{
    name      = "${{var.app_name}}-container"
    image     = "nginx:latest"  # Replace with actual image
    essential = true

    portMappings = [{{
      containerPort = 80
      protocol      = "tcp"
    }}]

    logConfiguration = {{
      logDriver = "awslogs"
      options = {{
        "awslogs-group"         = aws_cloudwatch_log_group.{resource_name}.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }}
    }}
  }}])

  tags = var.tags
}}

# ECS Service
resource "aws_ecs_service" "{resource_name}" {{
  name            = "${{var.app_name}}-service"
  cluster         = aws_ecs_cluster.{resource_name}.id
  task_definition = aws_ecs_task_definition.{resource_name}.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {{
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.{resource_name}.id]
    assign_public_ip = false
  }}

  load_balancer {{
    target_group_arn = aws_lb_target_group.{resource_name}.arn
    container_name   = "${{var.app_name}}-container"
    container_port   = 80
  }}

  depends_on = [aws_lb_listener.{resource_name}]

  tags = var.tags
}}

# Application Load Balancer
resource "aws_lb" "{resource_name}" {{
  name               = "${{var.app_name}}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.{resource_name}_alb.id]
  subnets            = aws_subnet.public[*].id

  tags = var.tags
}}

resource "aws_lb_target_group" "{resource_name}" {{
  name        = "${{var.app_name}}-tg"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = aws_vpc.{resource_name}_vpc.id
  target_type = "ip"

  health_check {{
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }}

  tags = var.tags
}}

resource "aws_lb_listener" "{resource_name}" {{
  load_balancer_arn = aws_lb.{resource_name}.arn
  port              = 80
  protocol          = "HTTP"

  default_action {{
    type             = "forward"
    target_group_arn = aws_lb_target_group.{resource_name}.arn
  }}
}}

# VPC
resource "aws_vpc" "{resource_name}_vpc" {{
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-vpc"
  }})
}}

# Private Subnets
resource "aws_subnet" "private" {{
  count             = 2
  vpc_id            = aws_vpc.{resource_name}_vpc.id
  cidr_block        = cidrsubnet(aws_vpc.{resource_name}_vpc.cidr_block, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-private-${{count.index + 1}}"
  }})
}}

# Public Subnets
resource "aws_subnet" "public" {{
  count                   = 2
  vpc_id                  = aws_vpc.{resource_name}_vpc.id
  cidr_block              = cidrsubnet(aws_vpc.{resource_name}_vpc.cidr_block, 8, count.index + 2)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-public-${{count.index + 1}}"
  }})
}}

# Internet Gateway
resource "aws_internet_gateway" "{resource_name}_igw" {{
  vpc_id = aws_vpc.{resource_name}_vpc.id

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-igw"
  }})
}}

# NAT Gateway
resource "aws_eip" "{resource_name}_nat" {{
  count  = 2
  domain = "vpc"

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-nat-${{count.index + 1}}"
  }})
}}

resource "aws_nat_gateway" "{resource_name}_nat" {{
  count         = 2
  allocation_id = aws_eip.{resource_name}_nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-nat-${{count.index + 1}}"
  }})

  depends_on = [aws_internet_gateway.{resource_name}_igw]
}}

# Route Tables
resource "aws_route_table" "{resource_name}_public" {{
  vpc_id = aws_vpc.{resource_name}_vpc.id

  route {{
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.{resource_name}_igw.id
  }}

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-public-rt"
  }})
}}

resource "aws_route_table" "{resource_name}_private" {{
  count  = 2
  vpc_id = aws_vpc.{resource_name}_vpc.id

  route {{
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.{resource_name}_nat[count.index].id
  }}

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-private-rt-${{count.index + 1}}"
  }})
}}

resource "aws_route_table_association" "{resource_name}_public" {{
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.{resource_name}_public.id
}}

resource "aws_route_table_association" "{resource_name}_private" {{
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.{resource_name}_private[count.index].id
}}

# Security Groups
resource "aws_security_group" "{resource_name}" {{
  name        = "${{var.app_name}}-ecs-sg"
  description = "Security group for ECS tasks"
  vpc_id      = aws_vpc.{resource_name}_vpc.id

  ingress {{
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.{resource_name}_alb.id]
  }}

  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-ecs-sg"
  }})
}}

resource "aws_security_group" "{resource_name}_alb" {{
  name        = "${{var.app_name}}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = aws_vpc.{resource_name}_vpc.id

  ingress {{
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  tags = merge(var.tags, {{
    Name = "${{var.app_name}}-alb-sg"
  }})
}}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "{resource_name}" {{
  name              = "/ecs/${{var.app_name}}"
  retention_in_days = 7

  tags = var.tags
}}

# Data source for availability zones
data "aws_availability_zones" "available" {{
  state = "available"
}}

# IAM Roles
resource "aws_iam_role" "ecs_execution" {{
  name = "${{var.app_name}}-ecs-execution-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{
        Service = "ecs-tasks.amazonaws.com"
      }}
      Action = "sts:AssumeRole"
    }}]
  }})

  tags = var.tags
}}

resource "aws_iam_role_policy_attachment" "ecs_execution" {{
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}}

resource "aws_iam_role" "ecs_task" {{
  name = "${{var.app_name}}-ecs-task-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{
        Service = "ecs-tasks.amazonaws.com"
      }}
      Action = "sts:AssumeRole"
    }}]
  }})

  tags = var.tags
}}
'''

    def _generate_ecs_ec2(self, spec: IntentSpec, region: str, app_name: str) -> str:
        """Generate ECS EC2 infrastructure."""
        # Simplified version - can be expanded
        base = self._generate_ecs_fargate(spec, region, app_name)
        # Replace Fargate with EC2 launch type
        base = base.replace('launch_type     = "FARGATE"', 'launch_type     = "EC2"')
        base = base.replace('requires_compatibilities = ["FARGATE"]', 'requires_compatibilities = ["EC2"]')
        return base

    def _generate_lambda(self, spec: IntentSpec, region: str, app_name: str) -> str:
        """Generate Lambda function infrastructure."""
        function_name = app_name.replace("-", "_")

        return f'''# Lambda Function
resource "aws_lambda_function" "{function_name}" {{
  function_name = "${{var.app_name}}-function"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  filename         = "lambda_function.zip"
  source_code_hash = filebase64sha256("lambda_function.zip")

  environment {{
    variables = {{
      ENVIRONMENT = var.environment
      APP_NAME    = var.app_name
    }}
  }}

  tags = var.tags
}}

# API Gateway HTTP API
resource "aws_apigatewayv2_api" "{function_name}" {{
  name          = "${{var.app_name}}-api"
  protocol_type = "HTTP"

  tags = var.tags
}}

resource "aws_apigatewayv2_stage" "{function_name}" {{
  api_id = aws_apigatewayv2_api.{function_name}.id
  name   = "$default"

  auto_deploy = true

  tags = var.tags
}}

resource "aws_apigatewayv2_integration" "{function_name}" {{
  api_id           = aws_apigatewayv2_api.{function_name}.id
  integration_type = "AWS_PROXY"

  integration_method = "POST"
  integration_uri    = aws_lambda_function.{function_name}.invoke_arn
  payload_format_version = "2.0"
}}

resource "aws_apigatewayv2_route" "{function_name}" {{
  api_id    = aws_apigatewayv2_api.{function_name}.id
  route_key = "$default"

  target = "integrations/${{aws_apigatewayv2_integration.{function_name}.id}}"
}}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "{function_name}_api_gateway" {{
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.{function_name}.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${{aws_apigatewayv2_api.{function_name}.execution_arn}}/*/*"
}}

# IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_execution" {{
  name = "${{var.app_name}}-lambda-execution-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{
        Service = "lambda.amazonaws.com"
      }}
      Action = "sts:AssumeRole"
    }}]
  }})

  tags = var.tags
}}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {{
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "{function_name}" {{
  name              = "/aws/lambda/${{var.app_name}}-function"
  retention_in_days = 7

  tags = var.tags
}}
'''


def create_terraform_generator() -> TerraformGenerator:
    """Factory function for creating TerraformGenerator."""
    return TerraformGenerator()
