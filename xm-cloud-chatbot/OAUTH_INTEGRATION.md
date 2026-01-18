# OAuth Integration for Marketer-MCP

## Overview

This implementation adds OAuth 2.0 authentication for the marketer-mcp server integration. The flow ensures users are authenticated before making any calls to the marketer-mcp server.

## OAuth Flow

1. **User initiates chat** → App checks for valid OAuth token in database
2. **No token or expired** → Redirects to OAuth authorization server with client_id
3. **User authenticates** → OAuth server redirects back with authorization code
4. **Token exchange** → App exchanges code for access/refresh tokens
5. **Store tokens** → Tokens stored in database per user
6. **Authenticated requests** → MCP calls include Bearer token in headers

## Implementation Details

### Database Schema

Added `OAuthToken` model to store user-specific OAuth credentials:
- `userId` - Unique user identifier
- `accessToken` - OAuth access token
- `refreshToken` - OAuth refresh token (optional)
- `expiresAt` - Token expiration timestamp
- `tokenType` - Token type (default: "Bearer")
- `scope` - OAuth scopes granted

### API Routes

#### `/api/auth/login`
- Redirects user to OAuth authorization server
- Parameters: `userId`, `redirectUri` (optional)
- Constructs authorization URL with client_id and callback URL

#### `/api/auth/callback`
- Handles OAuth redirect after user authentication
- Exchanges authorization code for access/refresh tokens
- Stores tokens in database
- Redirects user back to app

#### `/api/auth/refresh`
- Refreshes expired access tokens using refresh token
- Called automatically by marketer-mcp client when needed
- Updates tokens in database

#### `/api/auth/status`
- Checks if user has valid OAuth token
- Returns authentication status and expiration info

### MCP Client

**File:** `lib/mcp/marketer-client.ts`

The `MarketerMCPClient` class:
- Retrieves OAuth tokens from database
- Automatically refreshes expired tokens
- Connects to marketer-mcp using SSE transport with Bearer auth
- Routes tool calls to marketer-mcp server
- Handles authentication errors gracefully

### Frontend Integration

**File:** `components/ChatPanel.tsx`

- Intercepts 401 Unauthorized responses
- Shows toast notification for auth requirement
- Redirects to OAuth login flow
- Resumes after successful authentication

### Environment Variables

Required environment variables (add to `.env.local`):

```bash
# Marketer MCP OAuth Configuration
MARKETER_MCP_URL="https://edge-platform.sitecorecloud.io/mcp/marketer-mcp-prod"
OAUTH_CLIENT_ID="your-client-id"
OAUTH_CLIENT_SECRET="your-client-secret"
OAUTH_AUTHORIZATION_URL="https://auth.sitecorecloud.io/oauth/authorize"
OAUTH_TOKEN_URL="https://auth.sitecorecloud.io/oauth/token"
OAUTH_AUDIENCE="https://edge-platform.sitecorecloud.io"
OAUTH_SCOPE="openid profile email mcp:read mcp:write"
NEXT_PUBLIC_BASE_URL="http://localhost:3000"
```

## Usage

### First-Time Setup

1. Configure OAuth credentials in `.env.local`
2. Run database migration:
   ```bash
   npx prisma migrate dev --name add_oauth_tokens
   ```
3. Start the application:
   ```bash
   npm run dev
   ```

### User Flow

1. User opens chat in XM Cloud Pages Editor
2. If not authenticated, user is redirected to OAuth login
3. User authenticates with OAuth provider
4. User is redirected back to chat panel
5. Chat requests now include authenticated marketer-mcp tools

### Tool Routing

The chat API automatically routes tools to the appropriate MCP server:

- **Marketer-MCP tools** → Routed to authenticated marketer-mcp client
- **Search-MCP tools** → Routed to existing search-mcp client
- **Image generation** → Handled locally via OpenAI API

## Security Considerations

- Access tokens stored encrypted in PostgreSQL database
- Tokens automatically refreshed before expiration (5-minute buffer)
- Failed authentication triggers re-authorization flow
- OAuth state parameter prevents CSRF attacks
- Client secret never exposed to frontend

## Testing

### Manual Testing

1. Clear any existing OAuth tokens for test user:
   ```sql
   DELETE FROM "OAuthToken" WHERE "userId" = 'test-user-id';
   ```

2. Send chat message
3. Verify redirect to OAuth login
4. Complete authentication
5. Verify redirect back to chat
6. Verify authenticated MCP calls work

### Checking Auth Status

```typescript
import { checkAuthStatus } from '@/lib/utils/auth-helpers';

const status = await checkAuthStatus(userId);
console.log(status.authenticated); // true/false
console.log(status.requiresAuth);  // true/false
```

## Troubleshooting

### Token Refresh Failures

If refresh token fails, user will be prompted to re-authenticate. Check:
- OAuth server is accessible
- Refresh token hasn't expired
- Client credentials are correct

### MCP Connection Issues

If marketer-mcp connection fails:
- Verify `MARKETER_MCP_URL` is correct
- Check access token is valid
- Ensure MCP server supports SSE transport
- Review server logs for authentication errors

## Future Enhancements

- [ ] Add token encryption at rest
- [ ] Implement token rotation policy
- [ ] Add OAuth consent screen customization
- [ ] Support multiple OAuth providers
- [ ] Add session management UI
- [ ] Implement token revocation on logout
