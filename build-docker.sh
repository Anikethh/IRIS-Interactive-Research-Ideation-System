#!/bin/bash

# IRIS Docker Build and Export Script
# This script builds the Docker image and exports it as a tar file for deployment

set -e

# Configuration
IMAGE_NAME="iris-web"
VERSION=${1:-latest}
TAR_FILE="iris-web-${VERSION}.tar"

echo "🔨 Building IRIS Docker image..."
echo "Image: ${IMAGE_NAME}:${VERSION}"

# Build the Docker image
docker build -t "${IMAGE_NAME}:${VERSION}" .

echo "✅ Docker image built successfully!"

# Export to tar file
echo "📦 Exporting Docker image to tar file..."
docker save -o "${TAR_FILE}" "${IMAGE_NAME}:${VERSION}"

echo "✅ Docker image exported to: ${TAR_FILE}"
echo "📊 File size:"

# Cross-platform file size display
if command -v ls &> /dev/null; then
    ls -lh "${TAR_FILE}"
elif command -v dir &> /dev/null; then
    dir "${TAR_FILE}"
else
    echo "File created: ${TAR_FILE}"
fi

echo ""
echo "🎉 Ready for deployment!"
echo "📋 Deployment package: ${TAR_FILE}"
echo "⚠️  Remember to provide environment variables to your infrastructure team"
echo ""
echo "Next steps for infrastructure team:"
echo "1. Load image: docker load -i ${TAR_FILE}"
echo "2. Tag for registry: docker tag ${IMAGE_NAME}:${VERSION} your-registry/${IMAGE_NAME}:${VERSION}"
echo "3. Push to registry: docker push your-registry/${IMAGE_NAME}:${VERSION}"