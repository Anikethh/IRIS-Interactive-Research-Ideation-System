@echo off
REM IRIS Docker Build and Export Script for Windows
REM This script builds the Docker image and exports it as a tar file for deployment

setlocal

REM Configuration
set IMAGE_NAME=iris-web
set VERSION=%1
if "%VERSION%"=="" set VERSION=latest
set TAR_FILE=iris-web-%VERSION%.tar

echo 🔨 Building IRIS Docker image...
echo Image: %IMAGE_NAME%:%VERSION%

REM Build the Docker image
docker build -t "%IMAGE_NAME%:%VERSION%" .
if %ERRORLEVEL% neq 0 (
    echo ❌ Docker build failed!
    exit /b 1
)

echo ✅ Docker image built successfully!

REM Export to tar file
echo 📦 Exporting Docker image to tar file...
docker save -o "%TAR_FILE%" "%IMAGE_NAME%:%VERSION%"
if %ERRORLEVEL% neq 0 (
    echo ❌ Docker save failed!
    exit /b 1
)

echo ✅ Docker image exported to: %TAR_FILE%
echo 📊 File size:
dir "%TAR_FILE%"

echo.
echo 🎉 Ready for deployment!
echo 📋 Deployment package: %TAR_FILE%
echo ⚠️  Remember to provide environment variables to your infrastructure team
echo.
echo Next steps for infrastructure team:
echo 1. Load image: docker load -i %TAR_FILE%
echo 2. Tag for registry: docker tag %IMAGE_NAME%:%VERSION% your-registry/%IMAGE_NAME%:%VERSION%
echo 3. Push to registry: docker push your-registry/%IMAGE_NAME%:%VERSION%

pause