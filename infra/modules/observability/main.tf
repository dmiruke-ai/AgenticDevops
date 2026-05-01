# =============================================================================
# Observability Module - CloudWatch Dashboards, Alarms, X-Ray
# =============================================================================

variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "ecs_cluster_name" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

data "aws_region" "current" {}

# =============================================================================
# CloudWatch Dashboard
# =============================================================================

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.name_prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # Header
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "# AI DevOps Agent Platform - AWS Observability"
        }
      },
      # ECS CPU Utilization
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "ECS CPU Utilization"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, { stat = "Average" }]
          ]
          view   = "timeSeries"
          period = 60
        }
      },
      # ECS Memory Utilization
      {
        type   = "metric"
        x      = 8
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "ECS Memory Utilization"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ECS", "MemoryUtilization", "ClusterName", var.ecs_cluster_name, { stat = "Average" }]
          ]
          view   = "timeSeries"
          period = 60
        }
      },
      # Running Tasks Count
      {
        type   = "metric"
        x      = 16
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Running Tasks"
          region = data.aws_region.current.name
          metrics = [
            ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", var.ecs_cluster_name, { stat = "Average" }]
          ]
          view = "singleValue"
        }
      },
      # API Logs
      {
        type   = "log"
        x      = 0
        y      = 7
        width  = 12
        height = 6
        properties = {
          title  = "API Logs (Recent)"
          region = data.aws_region.current.name
          query  = "SOURCE '/ecs/${var.name_prefix}' | fields @timestamp, @message | filter @logStream like /api/ | sort @timestamp desc | limit 50"
        }
      },
      # Error Logs
      {
        type   = "log"
        x      = 12
        y      = 7
        width  = 12
        height = 6
        properties = {
          title  = "Error Logs"
          region = data.aws_region.current.name
          query  = "SOURCE '/ecs/${var.name_prefix}' | fields @timestamp, @message | filter @message like /error|Error|ERROR/ | sort @timestamp desc | limit 50"
        }
      },
      # ALB Request Count
      {
        type   = "metric"
        x      = 0
        y      = 13
        width  = 8
        height = 6
        properties = {
          title  = "ALB Request Count"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", "${var.name_prefix}-alb", { stat = "Sum" }]
          ]
          view   = "timeSeries"
          period = 60
        }
      },
      # ALB Target Response Time
      {
        type   = "metric"
        x      = 8
        y      = 13
        width  = 8
        height = 6
        properties = {
          title  = "ALB Response Time"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", "${var.name_prefix}-alb", { stat = "Average" }]
          ]
          view   = "timeSeries"
          period = 60
        }
      },
      # ALB HTTP Error Codes
      {
        type   = "metric"
        x      = 16
        y      = 13
        width  = 8
        height = 6
        properties = {
          title  = "ALB HTTP 5XX Errors"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", "${var.name_prefix}-alb", { stat = "Sum" }],
            ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", "${var.name_prefix}-alb", { stat = "Sum" }]
          ]
          view   = "timeSeries"
          period = 60
        }
      }
    ]
  })
}

# =============================================================================
# CloudWatch Alarms
# =============================================================================

# High CPU Alarm
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${var.name_prefix}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "CPU utilization is above 80%"

  dimensions = {
    ClusterName = var.ecs_cluster_name
  }

  tags = var.tags
}

# High Memory Alarm
resource "aws_cloudwatch_metric_alarm" "memory_high" {
  alarm_name          = "${var.name_prefix}-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Memory utilization is above 80%"

  dimensions = {
    ClusterName = var.ecs_cluster_name
  }

  tags = var.tags
}

# 5XX Error Alarm
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.name_prefix}-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "More than 10 5XX errors in the last minute"
  treat_missing_data  = "notBreaching"

  tags = var.tags
}

# =============================================================================
# X-Ray Sampling Rule
# =============================================================================

resource "aws_xray_sampling_rule" "main" {
  rule_name      = "${var.name_prefix}-sampling"
  priority       = 1000
  reservoir_size = 5
  fixed_rate     = 0.1
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  version        = 1
  resource_arn   = "*"

  tags = var.tags
}

# =============================================================================
# Log Metric Filters
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "error_count" {
  name           = "${var.name_prefix}-error-count"
  pattern        = "ERROR"
  log_group_name = "/ecs/${var.name_prefix}"

  metric_transformation {
    name      = "ErrorCount"
    namespace = "DevOpsAgent"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "terraform_errors" {
  name           = "${var.name_prefix}-terraform-errors"
  pattern        = "[timestamp, level=ERROR, ..., message=*terraform*]"
  log_group_name = "/ecs/${var.name_prefix}"

  metric_transformation {
    name      = "TerraformErrorCount"
    namespace = "DevOpsAgent"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "intent_transitions" {
  name           = "${var.name_prefix}-intent-transitions"
  pattern        = "intent_transition"
  log_group_name = "/ecs/${var.name_prefix}"

  metric_transformation {
    name      = "IntentTransitionCount"
    namespace = "DevOpsAgent"
    value     = "1"
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "dashboard_url" {
  value = "https://${data.aws_region.current.name}.console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${var.name_prefix}-dashboard"
}

output "dashboard_name" {
  value = aws_cloudwatch_dashboard.main.dashboard_name
}
