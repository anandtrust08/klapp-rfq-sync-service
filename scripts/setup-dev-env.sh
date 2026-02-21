#!/bin/bash
# =============================================================================
# setup-dev-env.sh - Distribute AI API keys to per-service .env files
# =============================================================================
# Reads API keys from the central .env (klapp-ai-agent-rfq/docker/compose/.env)
# and injects them into per-service .env files for local development outside Docker.
#
# Usage:
#   ./scripts/setup-dev-env.sh
#
# When running services via Docker Compose, keys are injected automatically
# by docker-compose.yml - you do NOT need this script for Docker usage.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CENTRAL_ENV="$REPO_ROOT/klapp-ai-agent-rfq/docker/compose/.env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================="
echo "Klapp Dev Environment - API Key Distribution"
echo "============================================="
echo ""

# Check central .env exists
if [ ! -f "$CENTRAL_ENV" ]; then
    echo -e "${RED}ERROR: Central .env not found at:${NC}"
    echo "  $CENTRAL_ENV"
    echo ""
    echo "Copy from .env.example first:"
    echo "  cp $CENTRAL_ENV.example $CENTRAL_ENV"
    exit 1
fi

# Extract AI API keys from central .env
extract_key() {
    local key_name="$1"
    local value
    value=$(grep "^${key_name}=" "$CENTRAL_ENV" 2>/dev/null | head -1 | cut -d'=' -f2-)
    echo "$value"
}

GOOGLE_API_KEY=$(extract_key "GOOGLE_API_KEY")
ANTHROPIC_API_KEY=$(extract_key "ANTHROPIC_API_KEY")
OPENAI_API_KEY=$(extract_key "OPENAI_API_KEY")

echo "Keys found in central .env:"
[ -n "$GOOGLE_API_KEY" ] && echo -e "  ${GREEN}GOOGLE_API_KEY${NC}: ${GOOGLE_API_KEY:0:10}..." || echo -e "  ${YELLOW}GOOGLE_API_KEY${NC}: (empty)"
[ -n "$ANTHROPIC_API_KEY" ] && echo -e "  ${GREEN}ANTHROPIC_API_KEY${NC}: ${ANTHROPIC_API_KEY:0:15}..." || echo -e "  ${YELLOW}ANTHROPIC_API_KEY${NC}: (empty)"
[ -n "$OPENAI_API_KEY" ] && echo -e "  ${GREEN}OPENAI_API_KEY${NC}: ${OPENAI_API_KEY:0:10}..." || echo -e "  ${YELLOW}OPENAI_API_KEY${NC}: (empty)"
echo ""

# Function to inject/update a key in a .env file
inject_key() {
    local env_file="$1"
    local key_name="$2"
    local key_value="$3"

    if [ -z "$key_value" ]; then
        return
    fi

    if [ ! -f "$env_file" ]; then
        echo -e "  ${YELLOW}SKIP${NC}: $env_file (file not found)"
        return
    fi

    if grep -q "^${key_name}=" "$env_file" 2>/dev/null; then
        # Replace existing value (macOS-compatible sed)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^${key_name}=.*|${key_name}=${key_value}|" "$env_file"
        else
            sed -i "s|^${key_name}=.*|${key_name}=${key_value}|" "$env_file"
        fi
        echo -e "  ${GREEN}UPDATED${NC}: ${key_name} in $(basename "$(dirname "$env_file")")/$(basename "$env_file")"
    else
        # Append if not present
        echo "${key_name}=${key_value}" >> "$env_file"
        echo -e "  ${GREEN}ADDED${NC}: ${key_name} to $(basename "$(dirname "$env_file")")/$(basename "$env_file")"
    fi
}

# List of service .env files that need AI keys
declare -A SERVICE_ENVS=(
    ["klapp-email-processing-service"]="GOOGLE_API_KEY ANTHROPIC_API_KEY"
    ["klapp-marketplace/backend"]="GOOGLE_API_KEY"
    ["klapp-supplier-discovery"]="ANTHROPIC_API_KEY"
)

UPDATED_COUNT=0

for service_path in "${!SERVICE_ENVS[@]}"; do
    env_file="$REPO_ROOT/$service_path/.env"
    keys="${SERVICE_ENVS[$service_path]}"

    if [ ! -f "$env_file" ]; then
        echo -e "${YELLOW}SKIP${NC}: $service_path/.env (not found)"
        continue
    fi

    echo "Updating $service_path/.env:"
    for key in $keys; do
        case "$key" in
            GOOGLE_API_KEY)    inject_key "$env_file" "$key" "$GOOGLE_API_KEY" ;;
            ANTHROPIC_API_KEY) inject_key "$env_file" "$key" "$ANTHROPIC_API_KEY" ;;
            OPENAI_API_KEY)    inject_key "$env_file" "$key" "$OPENAI_API_KEY" ;;
        esac
    done
    UPDATED_COUNT=$((UPDATED_COUNT + 1))
    echo ""
done

echo "============================================="
echo -e "${GREEN}Done!${NC} Updated $UPDATED_COUNT service .env files."
echo ""

# Warnings for empty/placeholder keys
WARNINGS=0
if [ -z "$GOOGLE_API_KEY" ] || [[ "$GOOGLE_API_KEY" == *"YOUR_"* ]]; then
    echo -e "${YELLOW}WARNING${NC}: GOOGLE_API_KEY is empty or placeholder"
    WARNINGS=$((WARNINGS + 1))
fi
if [ -z "$ANTHROPIC_API_KEY" ] || [[ "$ANTHROPIC_API_KEY" == *"YOUR_"* ]]; then
    echo -e "${YELLOW}WARNING${NC}: ANTHROPIC_API_KEY is empty or placeholder"
    WARNINGS=$((WARNINGS + 1))
fi

if [ $WARNINGS -gt 0 ]; then
    echo ""
    echo "Set keys in: $CENTRAL_ENV"
fi
