#!/bin/bash

# Doorbell Intent Engine Setup Script

set -e

echo "================================================"
echo "Doorbell Intent Engine - Setup"
echo "================================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please don't run this script as root"
    exit 1
fi

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check for Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed"
    echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check for NVIDIA GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo "⚠️  Warning: nvidia-smi not found. GPU support may not work."
    echo "If you have an NVIDIA GPU, please install the drivers."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for NVIDIA Container Toolkit
if ! docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "⚠️  NVIDIA Container Toolkit not properly configured"
    echo ""
    echo "To install:"
    echo "  distribution=\$(. /etc/os-release;echo \$ID\$VERSION_ID)"
    echo "  curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -"
    echo "  curl -s -L https://nvidia.github.io/nvidia-docker/\$distribution/nvidia-docker.list | \\"
    echo "    sudo tee /etc/apt/sources.list.d/nvidia-docker.list"
    echo "  sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit"
    echo "  sudo systemctl restart docker"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✅ Prerequisites check passed"
echo ""

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    
    echo ""
    echo "⚠️  Please edit .env and configure these required variables:"
    echo "   - UNIFI_PROTECT_HOST"
    echo "   - UNIFI_PROTECT_TOKEN"
    echo "   - CAMERA_ID"
    echo ""
    read -p "Press enter to open .env in nano (or Ctrl+C to exit and edit manually)..."
    nano .env
fi

echo ""
echo "🐳 Pulling Docker images..."
docker-compose pull

echo ""
echo "🚀 Starting Ollama service..."
docker-compose up -d ollama

echo ""
echo "⏳ Waiting for Ollama to be ready..."
sleep 5

echo ""
echo "📥 Pulling Llama 3.2 3B model (this may take a few minutes)..."
docker exec doorbell-ollama ollama pull llama3.2:3b

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the full stack:"
echo "  docker-compose up -d"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f intent-engine"
echo ""
echo "To access the web UI:"
echo "  http://localhost:8080"
echo ""
echo "================================================"
