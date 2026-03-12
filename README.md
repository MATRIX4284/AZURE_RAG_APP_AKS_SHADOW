# AZURE_RAG_APP

Agentic RAG system with Azure Blob Storage and Event Grid integration.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure environment variables in `.env`.

## Testing

Run tests locally:
```bash
PYTHONPATH=. pytest tests/
```

## Docker

Build the image:
```bash
docker build -t azure-rag-app .
```

Run the container:
```bash
docker run -d \
  --name rag-consumer \
  --env-file .env \
  azure-rag-app
```

## CI/CD & Deployment

This repository uses GitHub Actions for automated testing, Docker build, and deployment to Azure Container Apps.

### Required GitHub Secrets

To enable the full pipeline, add the following secrets to your GitHub repository (**Settings > Secrets and variables > Actions**):

#### Azure Deployment
- `AZURE_CREDENTIALS`: Service Principal JSON (output of `az ad sp create-for-rbac`).
- `AZURE_STORAGE_CONNECTION_STRING`: Your Azure Storage connection string.
- `AZURE_CONTAINER_REGISTRY_LOGIN_SERVER`: e.g., `kaustavcontainerregistry.azurecr.io`
- `AZURE_CONTAINER_REGISTRY_USERNAME`: Service Principal App ID or ACR Admin Username.
- `AZURE_CONTAINER_REGISTRY_PASSWORD`: Service Principal Secret or ACR Admin Password.
- `AZURE_RESOURCE_GROUP`: Your Azure Resource Group name.
- `AZURE_CONTAINER_APPS_ENVIRONMENT`: Your Container Apps Environment name.

#### Email Notifications
- `MAIL_SERVER`: Your SMTP server address (e.g., `smtp.gmail.com`).
- `MAIL_PORT`: SMTP port (usually `465` for SSL or `587` for TLS).
- `MAIL_USERNAME`: Your email address.
- `MAIL_PASSWORD`: Your email password or App Password.
- `MAIL_RECEIVER`: The email address to receive notifications.
