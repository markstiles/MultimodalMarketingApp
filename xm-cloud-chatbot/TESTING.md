# Local Testing Guide

## Quick Start (Without MCP)

1. **Install dependencies:**
```bash
npm install
```

2. **Set up minimal environment:**
```bash
# Copy .env to .env.local
cp .env .env.local

# Edit .env.local and add ONLY:
OPENAI_API_KEY="sk-your-key"
POSTGRES_URL="postgresql://localhost:5432/test"  # or Vercel Postgres URL
```

3. **Skip database for now (test without persistence):**

Comment out database calls in `app/api/chat/route.ts` temporarily:
- Lines 25-50: Comment out conversation creation/retrieval
- Lines 70-78: Comment out message saving
- Lines 192-212: Comment out analytics tracking

4. **Start dev server:**
```bash
npm run dev
```

5. **Test the interface:**
- Open http://localhost:3000/editor-panel
- Type a message (without MCP tools, it will just chat)

## Full Local Testing (With Everything)

### Step 1: Database Setup

**Using Vercel Postgres (Recommended):**
```bash
vercel login
vercel link
vercel env pull .env.local
npx prisma migrate dev
```

**Using Local PostgreSQL:**
```bash
# Install PostgreSQL, then:
createdb xm_chatbot
# Update .env.local with connection string
npx prisma migrate dev
```

### Step 2: Run MCP Server Locally

In a **separate terminal**:

```bash
cd "c:\Users\marks\Desktop\Personal\Multimodal Marketing\xm-cloud-chatbot"

# Set environment variables for this terminal session
$env:SITECORE_DOMAIN_ID="your-domain-id"
$env:SITECORE_CLIENT_KEY="your-client-key"
$env:SITECORE_API_KEY="your-api-key"

# Run the MCP server
npx -y @markstiles/sitecore-search-mcp
```

This will start the MCP server on stdio. Keep this terminal open.

### Step 3: Update MCP Client for Local Testing

The current client uses stdio transport, which works for local testing. No changes needed if MCP server is running.

### Step 4: Start Next.js App

In your **main terminal**:

```bash
npm run dev
```

### Step 5: Test the Full Flow

1. Open http://localhost:3000/editor-panel
2. The interface will load with mock editor context
3. Try these test prompts:
   - "Audit the content on the site" (Content Auditor)
   - "Help me design a campaign" (Campaign Designer)
   - "Optimize this page for SEO" (SEO Optimizer)
   - "Create text for a hero banner" (Component Populator)

4. Watch the assistant badge change as intent is detected
5. Check Prisma Studio to see database records: `npx prisma studio`

## Testing Without XM Cloud Editor

Since you don't have XM Cloud yet, the app provides mock context. You can modify `app/editor-panel/page.tsx` to set test context:

```typescript
// For local testing, provide mock context
const [editorContext, setEditorContext] = useState<EditorContext>({
  pageId: 'test-page-123',
  siteId: 'test-site-456',
  userId: 'test-user-789',
  siteName: 'Test Site'
});
```

## Troubleshooting

**"Cannot connect to database"**
- Run `npx prisma studio` to verify connection
- Check POSTGRES_URL format
- Use `npx prisma migrate reset` to reset database

**"MCP connection failed"**
- Make sure MCP server terminal is still running
- Check Sitecore credentials are valid
- For testing, you can disable MCP tools temporarily

**"OpenAI API error"**
- Verify API key is valid: https://platform.openai.com/api-keys
- Check you have credits available
- Ensure no extra spaces in the key

**TypeScript errors**
- Run `npx prisma generate` to regenerate Prisma client
- Restart VS Code TypeScript server: Ctrl+Shift+P → "Restart TS Server"

## Testing Checklist

- [ ] Database connected (run `npx prisma studio`)
- [ ] OpenAI API key working (test at platform.openai.com)
- [ ] MCP server running (check terminal output)
- [ ] Next.js dev server running (`npm run dev`)
- [ ] Can send messages in chat
- [ ] Assistant badge shows and changes
- [ ] Conversations persist (check Prisma Studio)
- [ ] Chat history sidebar works

## Next Steps After Local Testing

1. Deploy MCP server to Railway (see `railway-mcp-server/README.md`)
2. Deploy Next.js app to Vercel (`vercel deploy`)
3. Configure XM Cloud editor extension with production URL
4. Test in actual XM Cloud Pages Editor
