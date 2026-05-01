#!/bin/bash
# =============================================================================
# Expose local services to web using Cloudflare Tunnel
# =============================================================================

set -e

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /tmp/cloudflared
    chmod +x /tmp/cloudflared
    sudo mv /tmp/cloudflared /usr/local/bin/cloudflared
fi

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Exposing AI DevOps Agent Platform to Web                        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Create a config file for multiple services
cat > /tmp/cloudflared-config.yml << EOF
tunnel: devops-agent-demo
ingress:
  - hostname: api.devops-demo.com
    service: http://localhost:8000
  - hostname: grafana.devops-demo.com
    service: http://localhost:3010
  - hostname: jaeger.devops-demo.com
    service: http://localhost:16686
  - hostname: prometheus.devops-demo.com
    service: http://localhost:9090
  - service: http_status:404
EOF

echo "Starting Cloudflare Tunnel..."
echo ""
echo "Services will be available at:"
echo "  • API:        Run 'cloudflared tunnel --url http://localhost:8000'"
echo "  • Grafana:    Run 'cloudflared tunnel --url http://localhost:3010'"
echo "  • Jaeger:     Run 'cloudflared tunnel --url http://localhost:16686'"
echo ""
echo "For quick single-service tunnel:"
echo "  cloudflared tunnel --url http://localhost:8000"
echo ""

# Start tunnel for API (primary)
cloudflared tunnel --url http://localhost:8000
