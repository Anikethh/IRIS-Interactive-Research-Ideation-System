#!/bin/bash

# IRIS Docker Build and Push Script
# This script builds the Docker image and pushes it to Azure Container Registry

set -e

# Configuration
IMAGE_NAME="iris-web"
VERSION=${1:-latest}
REGISTRY_NAME=${AZURE_CONTAINER_REGISTRY:-"your-registry-name"}
REGISTRY_URL="${REGISTRY_NAME}.azurecr.io"

echo "🔨 Building IRIS Docker image..."
echo "Image: ${REGISTRY_URL}/${IMAGE_NAME}:${VERSION}"

# Build the Docker image
docker build -t "${IMAGE_NAME}:${VERSION}" .
docker tag "${IMAGE_NAME}:${VERSION}" "${REGISTRY_URL}/${IMAGE_NAME}:${VERSION}"

echo "✅ Docker image built successfully!"

# Optional: Push to Azure Container Registry
read -p "Do you want to push to Azure Container Registry? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Pushing to Azure Container Registry..."
    
    # Login to ACR (requires Azure CLI)
    az acr login --name "${REGISTRY_NAME}"
    
    # Push the image
    docker push "${REGISTRY_URL}/${IMAGE_NAME}:${VERSION}"
    
    echo "✅ Image pushed successfully!"
    echo "📋 Image URL: ${REGISTRY_URL}/${IMAGE_NAME}:${VERSION}"
else
    echo "ℹ️  Image built locally. To push later, run:"
    echo "   az acr login --name ${REGISTRY_NAME}"
    echo "   docker push ${REGISTRY_URL}/${IMAGE_NAME}:${VERSION}"
fi

echo "🎉 Build complete!"