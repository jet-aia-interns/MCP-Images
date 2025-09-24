# Azure Web App Deployment Guide for MCP Image Service

## Prerequisites

1. Azure subscription with access to create Web Apps
2. Azure CLI installed (`az login` completed)
3. Azure Storage Account created for blob storage
4. (Optional) GitHub account for CI/CD pipeline

## Environment Variables Required

The following environment variables need to be configured in your Azure Web App:

### Required Variables
- `AZURE_CONNECTION_STRING`: Your Azure Storage Account connection string
- `PORT`: Set to 8000 (automatically configured by Azure)

### Optional Variables
- `CHROME_BIN`: Path to Chrome binary (auto-configured in startup script)
- `CHROME_PATH`: Path to Chrome (auto-configured in startup script)

## Deployment Methods

### Method 1: Deploy using Azure CLI (Recommended)

1. **Create a Resource Group** (if you don't have one):
   ```bash
   az group create --name mcp-images-rg --location "East US"
   ```

2. **Create an App Service Plan**:
   ```bash
   az appservice plan create --name mcp-images-plan --resource-group mcp-images-rg --sku B1 --is-linux
   ```

3. **Create the Web App**:
   ```bash
   az webapp create --resource-group mcp-images-rg --plan mcp-images-plan --name mcp-images-app --runtime "PYTHON|3.11" --startup-file "startup.sh"
   ```

4. **Configure Environment Variables**:
   ```bash
   az webapp config appsettings set --resource-group mcp-images-rg --name mcp-images-app --settings \
     AZURE_CONNECTION_STRING="your_azure_storage_connection_string_here" \
     SCM_DO_BUILD_DURING_DEPLOYMENT=true \
     ENABLE_ORYX_BUILD=true
   ```

5. **Deploy the Code**:
   ```bash
   # From your project directory
   az webapp up --sku B1 --name mcp-images-app --resource-group mcp-images-rg --location "East US"
   ```

### Method 2: Deploy using Azure Portal

1. **Create Web App**:
   - Go to Azure Portal → Create a resource → Web App
   - Choose Linux OS and Python 3.11 runtime
   - Select appropriate pricing tier (B1 or higher recommended)

2. **Configure Deployment**:
   - Go to Deployment Center in your Web App
   - Choose your source (GitHub, Azure Repos, Local Git, etc.)
   - Configure the build provider (GitHub Actions or Azure Pipelines)

3. **Set Environment Variables**:
   - Go to Configuration → Application settings
   - Add the required environment variables listed above

4. **Upload Files**:
   - Use the deployment method configured in step 2
   - Ensure all files from your project are uploaded

## Testing Your Deployment

Once deployed, you can test your MCP Image Service:

1. **Health Check**:
   ```bash
   curl https://your-app-name.azurewebsites.net/
   ```

2. **List Available Tools**:
   ```bash
   curl https://your-app-name.azurewebsites.net/tools
   ```

3. **Search for Images**:
   ```bash
   curl -X POST https://your-app-name.azurewebsites.net/search_images \
     -H "Content-Type: application/json" \
     -d '{"query": "sunset", "max_results": 5}'
   ```

4. **Save an Image**:
   ```bash
   curl -X POST https://your-app-name.azurewebsites.net/save_image \
     -H "Content-Type: application/json" \
     -d '{"image_url": "https://example.com/image.jpg", "filename": "test-image"}'
   ```

## API Endpoints

Your deployed MCP Image Service will expose these REST endpoints:

- `GET /` - Health check
- `GET /tools` - List available MCP tools
- `POST /call_tool` - Execute any MCP tool
- `POST /search_images` - Search for images
- `POST /save_image` - Save an image to Azure Storage

## Troubleshooting

### Common Issues:

1. **Startup Timeout**: If your app takes too long to start, increase the startup timeout:
   ```bash
   az webapp config set --resource-group mcp-images-rg --name mcp-images-app --startup-file "startup.sh" --startup-timeout 120
   ```

2. **Chrome/Selenium Issues**: The startup script installs Chrome and ChromeDriver. If issues persist, check the app logs:
   ```bash
   az webapp log tail --resource-group mcp-images-rg --name mcp-images-app
   ```

3. **Memory Issues**: If you encounter memory problems, upgrade to a higher tier (B2 or higher):
   ```bash
   az appservice plan update --name mcp-images-plan --resource-group mcp-images-rg --sku B2
   ```

4. **Environment Variables**: Ensure all required environment variables are set correctly in the Azure Portal under Configuration → Application settings

### Monitoring and Logs:

- Check application logs in Azure Portal under Monitoring → Log stream
- Use Azure Application Insights for detailed monitoring
- Monitor resource usage in the Overview section

## Security Considerations

1. **HTTPS Only**: Enable HTTPS-only in the TLS/SSL settings
2. **Authentication**: Consider adding authentication for production use
3. **CORS**: The Flask app has CORS enabled - configure it appropriately for your use case
4. **Environment Variables**: Never commit sensitive environment variables to your repository

## Cost Optimization

- Use B1 tier for development/testing
- Scale up to B2/B3 for production with higher traffic
- Monitor usage and scale down when not needed
- Consider using consumption-based pricing for sporadic usage

## Next Steps

After successful deployment, consider:
1. Setting up custom domain names
2. Implementing authentication and authorization
3. Adding monitoring and alerting
4. Setting up automated backups
5. Implementing CI/CD pipeline (see next section)