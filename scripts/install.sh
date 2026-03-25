#!/bin/bash

# =============================================================================
# AI Lab Memory - Installation Script
# =============================================================================
# This script installs all dependencies for the AI Lab Memory System.
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

check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 is not installed"
        return 1
    fi
    return 0
}

# =============================================================================
# Prerequisites Check
# =============================================================================

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Python
    if ! check_command python3; then
        log_error "Python 3.12+ is required"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    log_success "Python $PYTHON_VERSION found"

    # Check Docker
    if ! check_command docker; then
        log_error "Docker is required"
        exit 1
    fi

    DOCKER_VERSION=$(docker --version | awk '{print $3}')
    log_success "Docker $DOCKER_VERSION found"

    # Check Git
    if ! check_command git; then
        log_error "Git is required"
        exit 1
    fi

    log_success "Git found"

    # Check NVIDIA driver (optional but recommended)
    if command -v nvidia-smi &> /dev/null; then
        GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader)
        log_success "NVIDIA GPU found: $GPU_INFO"
    else
        log_warning "No NVIDIA GPU found - embedding will be CPU-only (slow)"
    fi
}

# =============================================================================
# System Dependencies
# =============================================================================

install_system_deps() {
    log_info "Installing system dependencies..."

    # Detect package manager
    if command -v apt &> /dev/null; then
        log_info "Using apt package manager"
        sudo apt update
        sudo apt install -y \
            python3.12 \
            python3.12-venv \
            python3-pip \
            docker.io \
            docker-compose \
            curl \
            wget \
            build-essential \
            cmake \
            llama-server
        log_success "System dependencies installed"
    elif command -v dnf &> /dev/null; then
        log_info "Using dnf package manager"
        sudo dnf install -y \
            python3.12 \
            python3.12-venv \
            python3-pip \
            docker \
            docker-compose \
            curl \
            wget \
            gcc \
            gcc-c++ \
            make
        log_success "System dependencies installed"
    else
        log_warning "Unknown package manager - please install dependencies manually"
    fi
}

# =============================================================================
# Docker Setup
# =============================================================================

setup_docker() {
    log_info "Setting up Docker..."

    # Add user to docker group
    if ! groups $USER | grep -q docker; then
        log_info "Adding user to docker group"
        sudo usermod -aG docker $USER
        log_warning "You need to logout/login or run: newgrp docker"
    fi

    # Start Docker services
    if ! docker ps &> /dev/null; then
        log_info "Starting Docker service"
        sudo systemctl start docker
        sudo systemctl enable docker
        log_success "Docker service started"
    fi

    log_success "Docker setup complete"
}

# =============================================================================
# Python Virtual Environment
# =============================================================================

setup_venv() {
    log_info "Setting up Python virtual environment..."

    # Create venv for ai-mem
    if [ ! -d "venv" ]; then
        log_info "Creating ai-mem virtual environment"
        python3 -m venv venv
        log_success "ai-mem venv created"
    else
        log_success "ai-mem venv already exists"
    fi

    # Activate venv
    source venv/bin/activate

    # Upgrade pip
    log_info "Upgrading pip"
    pip install --upgrade pip

    # Install ai-mem dependencies
    if [ -f "ai-mem/requirements.txt" ]; then
        log_info "Installing ai-mem dependencies"
        pip install -r ai-mem/requirements.txt
        log_success "ai-mem dependencies installed"
    fi

    # Install ai-rag dependencies
    if [ -f "ai-rag/requirements.txt" ]; then
        log_info "Installing ai-rag dependencies"
        pip install -r ai-rag/requirements.txt
        log_success "ai-rag dependencies installed"
    fi

    # Deactivate venv
    deactivate
}

# =============================================================================
# Docker Services
# =============================================================================

start_docker_services() {
    log_info "Starting Docker services (Qdrant + Redis)..."

    # Create data directories
    mkdir -p data/qdrant data/redis

    # Start services
    if [ -f "docker-compose.yml" ]; then
        docker-compose up -d qdrant redis
        log_success "Docker services started"

        # Wait for services to be ready
        log_info "Waiting for services to be ready..."
        sleep 10

        # Verify Qdrant
        if curl -s http://localhost:6333/collections &> /dev/null; then
            log_success "Qdrant is ready"
        else
            log_error "Qdrant is not responding"
            exit 1
        fi

        # Verify Redis
        if docker exec redis redis-cli ping &> /dev/null; then
            log_success "Redis is ready"
        else
            log_error "Redis is not responding"
            exit 1
        fi
    else
        log_warning "docker-compose.yml not found - skipping Docker services"
    fi
}

# =============================================================================
# Download Models
# =============================================================================

download_models() {
    log_info "Downloading models..."

    # Create models directory
    mkdir -p models/embedding models/reranker

    # Download embedding model
    if [ ! -f "models/embedding/qwen3-embedding-0.6b-q8_0.gguf" ]; then
        log_info "Downloading Qwen3-Embedding-0.6B-Q8_0..."
        python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='Gideon531/Qwen3-Embedding-0.6B-Q8_0-GGUF',
    filename='qwen3-embedding-0.6b-q8_0.gguf',
    local_dir='models/embedding'
)
"
        log_success "Embedding model downloaded"
    else
        log_success "Embedding model already exists"
    fi

    # Download reranking model (optional)
    if [ ! -f "models/reranker/qwen3-reranker-0.6b-q8_0.gguf" ]; then
        log_info "Downloading Qwen3-Reranker-0.6B-Q8_0..."
        python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF',
    filename='qwen3-reranker-0.6b-q8_0.gguf',
    local_dir='models/reranker'
)
"
        log_success "Reranking model downloaded"
    else
        log_success "Reranking model already exists"
    fi
}

# =============================================================================
# Initialize Qdrant
# =============================================================================

init_qdrant() {
    log_info "Initializing Qdrant collection..."

    # Check if collection exists
    if curl -s http://localhost:6333/collections/ai_memory | grep -q "ai_memory"; then
        log_success "Qdrant collection already exists"
    else
        log_info "Creating ai_memory collection"
        curl -X PUT http://localhost:6333/collections/ai_memory \
          -H "Content-Type: application/json" \
          -d '{
            "vectors": {
              "dense": {"size": 1024, "distance": "Cosine"},
              "sparse": {"bm25": {}}
            }
          }'
        log_success "Qdrant collection created"
    fi
}

# =============================================================================
# Environment Setup
# =============================================================================

setup_environment() {
    log_info "Setting up environment..."

    # Create .env file if not exists
    if [ ! -f ".env" ]; then
        log_info "Creating .env file from example"
        cp .env.example .env
        log_warning "Please edit .env with your API keys"
    else
        log_success ".env file already exists"
    fi
}

# =============================================================================
# Shell Functions
# =============================================================================

install_shell_functions() {
    log_info "Installing shell functions..."

    # Check if should install to bashrc
    read -p "Install shell functions to ~/.bashrc? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Append to bashrc
        cat >> ~/.bashrc << 'EOF'

# AI Lab Memory Functions
ai-up() {
    source ~/.config/ai-lab/secrets.env
    systemctl --user is-active ai-mem.service >/dev/null 2>&1 || \
        systemctl --user start ai-mem.service
    echo "✅ ai-mem active on :8083"
}

ai-down() {
    echo "ℹ️  ai-mem.service is a permanent stack."
    echo "    To stop: systemctl --user stop ai-mem.service"
}

ai-stats() {
    source ~/.config/ai-lab/secrets.env
    memdev
    cd ~/ai-stack/projects/ai-mem
    python3 search.py stats
    deactivate
}

ai-search() {
    source ~/.config/ai-lab/secrets.env
    memdev
    cd ~/ai-stack/projects/ai-mem
    python3 search.py search "$@"
    deactivate
}

ai-reindex-idf() {
    memdev && cd ~/ai-stack/projects/ai-mem && python3 compute_idf.py && deactivate
}
EOF
        log_success "Shell functions installed to ~/.bashrc"
        log_info "Run 'source ~/.bashrc' to activate"
    else
        log_info "Skipping shell functions installation"
    fi
}

# =============================================================================
# Final Verification
# =============================================================================

verify_installation() {
    log_info "Verifying installation..."

    # Check ai-mem health
    if curl -s http://localhost:8083/health | grep -q "ok"; then
        log_success "ai-mem is healthy"
    else
        log_warning "ai-mem is not running (start with: systemctl --user start ai-mem.service)"
    fi

    # Check Qdrant
    if curl -s http://localhost:6333/collections/ai_memory | grep -q "ai_memory"; then
        log_success "Qdrant collection exists"
    else
        log_warning "Qdrant collection not found"
    fi

    # Check models
    if [ -f "models/embedding/qwen3-embedding-0.6b-q8_0.gguf" ]; then
        log_success "Embedding model exists"
    else
        log_warning "Embedding model not found"
    fi

    echo
    log_success "Installation complete!"
    echo
    echo "Next steps:"
    echo "  1. Edit .env with your API keys"
    echo "  2. Run: source ~/.bashrc (if you installed shell functions)"
    echo "  3. Start ai-mem: systemctl --user start ai-mem.service"
    echo "  4. Test: ai-search \"hello world\""
    echo
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo
    echo "========================================"
    echo "  AI Lab Memory - Installation Script"
    echo "========================================"
    echo

    check_prerequisites
    install_system_deps
    setup_docker
    setup_venv
    start_docker_services
    download_models
    init_qdrant
    setup_environment
    install_shell_functions
    verify_installation
}

# Run main function
main "$@"
