# IRIS Docker Build and Export Script for Windows PowerShell
# This script builds the Docker image and exports it as a tar file for deployment

param(
    [string]$Version = "latest"
)

# Configuration
$IMAGE_NAME = "iris-web"
$TAR_FILE = "iris-web-$Version.tar"

Write-Host "🔨 Building IRIS Docker image..." -ForegroundColor Green
Write-Host "Image: $IMAGE_NAME`:$Version"

# Build the Docker image
Write-Host "Building Docker image..." -ForegroundColor Yellow
try {
    docker build -t "$IMAGE_NAME`:$Version" .
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed with exit code $LASTEXITCODE"
    }
    Write-Host "✅ Docker image built successfully!" -ForegroundColor Green
}
catch {
    Write-Host "❌ Docker build failed: $_" -ForegroundColor Red
    exit 1
}

# Export to tar file
Write-Host "📦 Exporting Docker image to tar file..." -ForegroundColor Yellow
try {
    docker save -o $TAR_FILE "$IMAGE_NAME`:$Version"
    if ($LASTEXITCODE -ne 0) {
        throw "Docker save failed with exit code $LASTEXITCODE"
    }
    Write-Host "✅ Docker image exported to: $TAR_FILE" -ForegroundColor Green
}
catch {
    Write-Host "❌ Docker save failed: $_" -ForegroundColor Red
    exit 1
}

# Show file info
Write-Host "📊 File information:" -ForegroundColor Cyan
$fileInfo = Get-Item $TAR_FILE
Write-Host "Size: $([math]::Round($fileInfo.Length / 1MB, 2)) MB"
Write-Host "Created: $($fileInfo.CreationTime)"

Write-Host ""
Write-Host "🎉 Ready for deployment!" -ForegroundColor Green
Write-Host "📋 Deployment package: $TAR_FILE" -ForegroundColor Cyan
Write-Host "⚠️  Remember to provide environment variables to your infrastructure team" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next steps for infrastructure team:" -ForegroundColor White
Write-Host "1. Load image: docker load -i $TAR_FILE"
Write-Host "2. Tag for registry: docker tag $IMAGE_NAME`:$Version your-registry/$IMAGE_NAME`:$Version"
Write-Host "3. Push to registry: docker push your-registry/$IMAGE_NAME`:$Version"

Read-Host "Press Enter to continue"