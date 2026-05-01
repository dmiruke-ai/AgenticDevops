# =============================================================================
# AI DevOps Agent Platform - AWS Infrastructure
# =============================================================================
# ECS Fargate deployment with full observability stack
# Region: us-east-1
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # Uncomment for remote state (recommended for production)
  # backend "s3" {
  #   bucket         = "agentic-devops-terraform-state"
  #   key            = "infra/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "agentic-devops"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# =============================================================================
# Data Sources
# =============================================================================

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# =============================================================================
# Random suffix for unique naming
# =============================================================================

resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  name_prefix = "devops-agent-${var.environment}"
  name_suffix = random_id.suffix.hex

  common_tags = {
    Project     = "agentic-devops"
    Environment = var.environment
  }
}

# =============================================================================
# VPC Module
# =============================================================================

module "vpc" {
  source = "./modules/vpc"

  name_prefix        = local.name_prefix
  vpc_cidr           = var.vpc_cidr
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 2)

  tags = local.common_tags
}

# =============================================================================
# Secrets Manager - Store API Keys
# =============================================================================

module "secrets" {
  source = "./modules/secrets"

  name_prefix      = local.name_prefix
  anthropic_api_key = var.anthropic_api_key
  openai_api_key    = var.openai_api_key

  tags = local.common_tags
}

# =============================================================================
# Application Load Balancer
# =============================================================================

module "alb" {
  source = "./modules/alb"

  name_prefix       = local.name_prefix
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids

  tags = local.common_tags
}

# =============================================================================
# ECS Cluster and Services
# =============================================================================

module "ecs" {
  source = "./modules/ecs"

  name_prefix         = local.name_prefix
  vpc_id              = module.vpc.vpc_id
  private_subnet_ids  = module.vpc.private_subnet_ids
  alb_security_group_id = module.alb.security_group_id

  # Target groups from ALB
  api_target_group_arn     = module.alb.api_target_group_arn
  grafana_target_group_arn = module.alb.grafana_target_group_arn

  # Secrets
  anthropic_secret_arn = module.secrets.anthropic_secret_arn
  openai_secret_arn    = module.secrets.openai_secret_arn

  # Container images
  api_image     = var.api_image
  grafana_image = var.grafana_image

  # Service discovery
  service_discovery_namespace_id = module.vpc.service_discovery_namespace_id

  tags = local.common_tags
}

# =============================================================================
# Observability Stack
# =============================================================================

module "observability" {
  source = "./modules/observability"

  name_prefix        = local.name_prefix
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  ecs_cluster_name   = module.ecs.cluster_name

  tags = local.common_tags
}
