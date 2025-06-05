# IRIS Docker Deployment Guide

## Overview
This document provides instructions for deploying the IRIS Interactive Research Ideation System using Docker on Azure Container Instances (ACI).

## Package Contents
- `iris-web-latest.tar` - Docker image file
- This deployment guide

## Prerequisites
- Docker installed on deployment machine
- Azure CLI (if using Azure Container Registry)
- Access to Azure Container Instances

## Environment Variables Required
The following environment variables must be configured:

### Required for Production (DEPLOY=true)
```bash
DEPLOY=true
FLASK_ENV=production
FLASK_SECRET_KEY=<generate-secure-random-key>

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=<your-azure-openai-key>
AZURE_OPENAI_ENDPOINT=<your-azure-endpoint>
AZURE_OPENAI_API_VERSION=2024-06-01

# Additional API Keys
SEMANTIC_SCHOLAR_API_KEY=<semantic-scholar-key>
HUGGINGFACE_API_KEY=<huggingface-key>
```

## Deployment Steps

### 1. Load Docker Image
```bash
docker load -i iris-web-latest.tar
```

### 2. Tag for Registry (if using Azure Container Registry)
```bash
docker tag iris-web:latest your-registry.azurecr.io/iris-web:latest
```

### 3. Push to Registry
```bash
az acr login --name your-registry
docker push your-registry.azurecr.io/iris-web:latest
```

### 4. Deploy to Azure Container Instances
```bash
az container create \
  --resource-group your-resource-group \
  --name iris-web \
  --image your-registry.azurecr.io/iris-web:latest \
  --dns-name-label iris-web-unique \
  --ports 5000 \
  --environment-variables \
    DEPLOY=true \
    FLASK_ENV=production \
    FLASK_SECRET_KEY="your-secret-key" \
    AZURE_OPENAI_API_KEY="your-key" \
    AZURE_OPENAI_ENDPOINT="your-endpoint" \
    AZURE_OPENAI_API_VERSION="2024-06-01" \
    SEMANTIC_SCHOLAR_API_KEY="your-key" \
    HUGGINGFACE_API_KEY="your-key"
```

## Application Details
- **Port**: 5000
- **Health Check**: Available at `/` endpoint  
- **Persistent Storage**: Optional volumes for uploads, logs, secure_keys
- **Resource Requirements**: Recommend 2GB RAM minimum for ML models

## Security Notes
- All API keys must be provided as environment variables
- No sensitive data is included in the Docker image
- Use Azure Key Vault for production key management
- Generate a strong FLASK_SECRET_KEY for session security

## Troubleshooting
- Check container logs: `az container logs --resource-group <rg> --name iris-web`
- Health check endpoint: `http://your-app-url/`
- Application runs on port 5000 internally