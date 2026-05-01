# =============================================================================
# Secrets Module - AWS Secrets Manager
# =============================================================================

variable "name_prefix" {
  type = string
}

variable "anthropic_api_key" {
  type      = string
  sensitive = true
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "tags" {
  type    = map(string)
  default = {}
}

# =============================================================================
# Anthropic API Key Secret
# =============================================================================

resource "aws_secretsmanager_secret" "anthropic" {
  name                    = "${var.name_prefix}/anthropic-api-key"
  description             = "Anthropic API key for Claude"
  recovery_window_in_days = 0  # Immediate deletion for demo

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "anthropic" {
  secret_id     = aws_secretsmanager_secret.anthropic.id
  secret_string = var.anthropic_api_key
}

# =============================================================================
# OpenAI API Key Secret
# =============================================================================

resource "aws_secretsmanager_secret" "openai" {
  name                    = "${var.name_prefix}/openai-api-key"
  description             = "OpenAI API key (fallback)"
  recovery_window_in_days = 0  # Immediate deletion for demo

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "openai" {
  secret_id     = aws_secretsmanager_secret.openai.id
  secret_string = var.openai_api_key
}

# =============================================================================
# Outputs
# =============================================================================

output "anthropic_secret_arn" {
  value = aws_secretsmanager_secret.anthropic.arn
}

output "openai_secret_arn" {
  value = aws_secretsmanager_secret.openai.arn
}
