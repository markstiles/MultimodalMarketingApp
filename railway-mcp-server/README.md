# Sitecore Search MCP Server - Railway Deployment

This folder contains the configuration for deploying the Sitecore Search MCP server on Railway.

## Setup Instructions

1. **Create a Railway account** at https://railway.app

2. **Create a new project** in Railway

3. **Add environment variables** in Railway dashboard:
   - `SITECORE_DOMAIN_ID` - Your Sitecore domain ID (second part of client key)
   - `SITECORE_CLIENT_KEY` - Full client key format `companyId-domainId`
   - `SITECORE_API_KEY` - Your Sitecore API key (optional if using subdomain auth)

4. **Deploy from GitHub**:
   - Push this folder to a GitHub repository
   - Connect Railway to your GitHub repo
   - Set the root directory to `railway-mcp-server`
   - Railway will automatically detect and run `npm start`

5. **Get your Railway URL**:
   - After deployment, Railway will provide a URL like `https://your-app.railway.app`
   - Update the `MCP_SERVER_URL` in your Next.js app's `.env` file

## Environment Variables

```env
SITECORE_DOMAIN_ID=12345678
SITECORE_CLIENT_KEY=123456789-12345678
SITECORE_API_KEY=01-xxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Testing the Deployment

Once deployed, the MCP server will be running and ready to accept connections from your Next.js chatbot application.

You can verify it's running by checking the Railway logs.

## Alternative: Using Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Set environment variables
railway variables set SITECORE_DOMAIN_ID=12345678
railway variables set SITECORE_CLIENT_KEY=123456789-12345678
railway variables set SITECORE_API_KEY=01-xxxxxxxx...

# Deploy
railway up
```

## Cost

Railway provides $5/month in free credits, which should be sufficient for low-traffic use cases.

For production use with higher traffic, consider upgrading to a paid plan.
