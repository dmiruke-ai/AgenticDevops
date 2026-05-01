# =============================================================================
# Outputs
# =============================================================================

output "api_url" {
  description = "URL for the API endpoint"
  value       = "http://${module.alb.alb_dns_name}"
}

output "grafana_url" {
  description = "URL for Grafana dashboard"
  value       = "http://${module.alb.alb_dns_name}:3000"
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = module.alb.alb_dns_name
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for ECS tasks"
  value       = module.ecs.log_group_name
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = module.observability.dashboard_url
}
