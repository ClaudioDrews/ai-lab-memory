#!/bin/bash

# =============================================================================
# AI Lab Memory - Configuration Script
# =============================================================================
# This script configures the AI Lab Memory System after installation.
# =============================================================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Configure Environment
# =============================================================================

configure_env() {
    log_info "Configuring environment variables..."

    ENV_FILE=".env"

    # Create directory if not exists
    mkdir -p $(dirname $ENV_FILE)

    # Create secrets.env if not exists
    if [ ! -f "$ENV_FILE" ]; then
        log_info "Creating secrets.env file"
        cat > $ENV_FILE << 'EOF'
# === LLM Providers ===
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
MISTRAL_API_KEY=
CEREBRAS_API_KEY=

# === HuggingFace ===
HF_TOKEN=

# === GitHub ===
GITHUB_TOKEN=

# === ai-mem ===
AI_MEM_API_KEY=sk-local
AI_MEM_BACKEND=http://localhost:11434
AI_MEM_TOP_K=5

# === Ollama ===
OLLAMA_HOST="http://localhost:11434"
OLLAMA_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CLOUD_HOST=https://ollama.com

# === Other Services ===
QDRANT_URI=http://localhost:6333
REDIS_HOST=localhost
REDIS_PORT=6379
EOF
        log_success "secrets.env created"
        log_warning "Please edit $ENV_FILE with your API keys"
    else
        log_success "secrets.env already exists"
    fi

    # Set permissions
    chmod 600 $ENV_FILE
    log_success "secrets.env permissions set (600)"
}

# =============================================================================
# Configure ai-mem
# =============================================================================

configure_ai_mem() {
    log_info "Configuring ai-mem..."

    CONFIG_FILE="ai-lab-memory/ai-mem/config.yaml"

    if [ -f "$CONFIG_FILE" ]; then
        log_success "ai-mem config found"

        # Verify configuration
        if grep -q "port: 8083" "$CONFIG_FILE"; then
            log_success "ai-mem port configured (8083)"
        else
            log_warning "ai-mem port not configured"
        fi
    else
        log_warning "ai-mem config not found at $CONFIG_FILE"
    fi
}

# =============================================================================
# Configure Shell
# =============================================================================

configure_shell() {
    log_info "Configuring shell..."

    # Check if shell config exists
    if [ -f "your-shell-config-dir/common.sh" ]; then
        log_success "Shell configuration found"
    else
        log_info "Creating shell configuration directory"
        mkdir -p your-shell-config-dir

        # Create common.sh
        cat > your-shell-config-dir/common.sh << 'EOF'
# =============================================================================
# LOADER CENTRAL - AI Laboratory Shell
# =============================================================================

SHELL_CONFIG_DIR="your-shell-config-dir"

# -----------------------------------------------------------------------------
# Load modules if exist
# -----------------------------------------------------------------------------
[ -f "$SHELL_CONFIG_DIR/aliases.sh" ] && source "$SHELL_CONFIG_DIR/aliases.sh"
[ -f "$SHELL_CONFIG_DIR/exports.sh" ] && source "$SHELL_CONFIG_DIR/exports.sh"
[ -f "$SHELL_CONFIG_DIR/functions.sh" ] && source "$SHELL_CONFIG_DIR/functions.sh"

# -----------------------------------------------------------------------------
# FZF Bindings (if installed)
# -----------------------------------------------------------------------------
if [ -f ~/.fzf.bash ]; then
    source ~/.fzf.bash
fi

# -----------------------------------------------------------------------------
# Zoxide (if installed)
# -----------------------------------------------------------------------------
if command -v zoxide &>/dev/null; then
    eval "$(zoxide init bash)"
fi
EOF
        log_success "Shell configuration created"
    fi
}

# =============================================================================
# Configure Hermes Agent (Optional)
# =============================================================================

configure_hermes() {
    log_info "Configuring Hermes Agent integration..."

    read -p "Configure Hermes Agent? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Check if Hermes is installed
        if command -v hermes &> /dev/null; then
            log_info "Hermes Agent found"

            # Configure Hermes
            hermes config set model.base_url "http://localhost:8083/v1" 2>/dev/null || true
            hermes config set model.provider "auto" 2>/dev/null || true
            hermes config set model.default "kimi-k2.5:cloud" 2>/dev/null || true

            log_success "Hermes Agent configured"

            # Add to Hermes .env
            HERMES_ENV="hermes-env-file"
            if [ -f "$HERMES_ENV" ]; then
                if ! grep -q "AI_MEM_API_KEY" "$HERMES_ENV"; then
                    echo 'AI_MEM_API_KEY=sk-local' >> "$HERMES_ENV"
                    echo 'OPENAI_BASE_URL=http://localhost:8083/v1' >> "$HERMES_ENV"
                    echo 'OPENAI_API_KEY=sk-local' >> "$HERMES_ENV"
                    log_success "Hermes .env updated"
                else
                    log_success "Hermes .env already configured"
                fi
            fi
        else
            log_warning "Hermes Agent not installed - skipping"
        fi
    else
        log_info "Skipping Hermes Agent configuration"
    fi
}

# =============================================================================
# Start Services
# =============================================================================

start_services() {
    log_info "Starting services..."

    # Start Docker services
    if command -v docker-compose &> /dev/null; then
        if [ -f "your-docker-compose-dir/docker-compose.yml" ]; then
            log_info "Starting Qdrant and Redis"
            cd your-docker-compose-dir
            docker-compose up -d qdrant redis
            log_success "Docker services started"
        fi
    fi

    # Start ai-mem service
    if command -v systemctl &> /dev/null; then
        log_info "Starting ai-mem service"
        systemctl --user start ai-mem.service 2>/dev/null || \
            log_warning "ai-mem service not configured (systemd)"
    fi
}

# =============================================================================
# Verification
# =============================================================================

verify_configuration() {
    log_info "Verifying configuration..."

    # Check ai-mem
    if curl -s http://localhost:8083/health | grep -q "ok"; then
        log_success "ai-mem is running"
    else
        log_warning "ai-mem is not running"
    fi

    # Check Qdrant
    if curl -s http://localhost:6333/collections | grep -q "ai_memory"; then
        log_success "Qdrant is running"
    else
        log_warning "Qdrant is not running"
    fi

    # Check Redis
    if docker exec redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
        log_success "Redis is running"
    else
        log_warning "Redis is not running"
    fi

    # Check embedding
    if curl -s http://localhost:8081/v1/models | grep -q "qwen3-embedding"; then
        log_success "Embedding server is running"
    else
        log_warning "Embedding server is not running"
    fi
}

# =============================================================================
# Usage Information
# =============================================================================

show_usage() {
    echo
    echo "========================================"
    echo "  Configuration Complete!"
    echo "========================================"
    echo
    echo "Next steps:"
    echo "  1. Edit secrets.env with your API keys:"
    echo "     nano .env"
    echo
    echo "  2. Start services:"
    echo "     systemctl --user start ai-mem.service"
    echo
    echo "  3. Test search:"
    echo "     ai-search \"hello world\""
    echo
    echo "  4. Integrate Hermes (if configured):"
    echo "     hermes chat -q \"What is RAG?\""
    echo
    echo "Documentation:"
    echo "  - Architecture: docs/architecture.md"
    echo "  - Installation: docs/installation.md"
    echo "  - Configuration: docs/configuration.md"
    echo "  - Usage: docs/usage.md"
    echo
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo
    echo "========================================"
    echo "  AI Lab Memory - Configuration Script"
    echo "========================================"
    echo

    configure_env
    configure_ai_mem
    configure_shell
    configure_hermes
    start_services
    verify_configuration
    show_usage
}

# Run main function
main "$@"
