# GitHub Actions CI/CD Setup for Azure Web App

## Prerequisites

1. Azure Web App already created (follow AZURE_DEPLOYMENT.md first)
2. GitHub repository with your MCP Image Service code
3. Azure CLI installed locally

## Setup Instructions

### 1. Get Publish Profile from Azure

```bash
# Download the publish profile for your web app
az webapp deployment list-publishing-profiles --resource-group mcp-images-rg --name mcp-images-app --xml
```

### 2. Add GitHub Secrets

In your GitHub repository, go to Settings → Secrets and variables → Actions, and add:

- **AZUREAPPSERVICE_PUBLISHPROFILE**: The entire XML content from step 1

### 3. Update Workflow Configuration

Edit `.github/workflows/deploy-azure.yml` and update:
- `AZURE_WEBAPP_NAME`: Replace with your actual Azure Web App name
- `PYTHON_VERSION`: Ensure it matches your Azure Web App runtime

### 4. Configure Environment Variables in Azure

Make sure these are set in your Azure Web App (Configuration → Application settings):
- `AZURE_CONNECTION_STRING`: Your Azure Storage connection string
- Any other environment variables your MCP service needs

### 5. Test the Pipeline

1. **Push to main branch**: The workflow will automatically trigger on push to main
2. **Manual trigger**: Go to Actions tab in GitHub → Deploy MCP Image Service to Azure Web App → Run workflow
3. **PR testing**: The workflow will build (but not deploy) on pull requests

## Workflow Features

### Build Job
- ✅ Sets up Python environment
- ✅ Installs dependencies
- ✅ Runs tests (add your tests as needed)
- ✅ Creates deployment artifact

### Deploy Job
- ✅ Only runs on main branch pushes
- ✅ Downloads build artifact
- ✅ Deploys to Azure Web App
- ✅ Tests deployment health

## Monitoring Deployments

1. **GitHub Actions**: Check the Actions tab for build/deploy status
2. **Azure Portal**: Monitor deployment in Deployment Center
3. **Application Logs**: Check logs in Azure Portal → Log stream

## Advanced Configuration

### Branch Protection
Protect your main branch:
1. Go to Settings → Branches
2. Add rule for main branch
3. Require status checks to pass
4. Require pull request reviews

### Environment Secrets
For multiple environments (dev/staging/prod):
1. Create GitHub Environments
2. Add environment-specific secrets
3. Modify workflow to use different environments

### Notifications
Add Slack/Teams notifications:
```yaml
- name: 'Notify on success'
  if: success()
  uses: 8398a7/action-slack@v3
  with:
    status: success
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Troubleshooting

### Common Issues:

1. **Authentication Failed**: Check publish profile in GitHub secrets
2. **Build Fails**: Check dependencies in requirements.txt
3. **Deployment Timeout**: Increase timeout in Azure Web App settings
4. **Environment Variables**: Ensure all required vars are set in Azure

### Debug Steps:

1. Check GitHub Actions logs
2. Check Azure Web App deployment logs
3. Test endpoints manually after deployment
4. Review Azure Application Insights (if enabled)

## Security Best Practices

1. **Secrets Management**: Never commit secrets to code
2. **Branch Protection**: Require reviews for main branch
3. **Environment Separation**: Use different apps for dev/staging/prod
4. **Monitoring**: Enable Application Insights and alerts
5. **Dependencies**: Regularly update dependencies and scan for vulnerabilities

## Cost Optimization

- Use deployment slots for zero-downtime deployments
- Scale down non-production environments when not in use
- Use staging slots for testing before production deployment