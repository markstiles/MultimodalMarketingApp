# XM Cloud Chatbot

AI-powered chatbot assistant for Sitecore XM Cloud Pages Editor. Provides intelligent content auditing, campaign design, SEO optimization, and component population capabilities.

## Features

- 🤖 **AI-Powered Assistants** - Four specialized assistant types with automatic intent classification
  - Content Auditor - Analyzes existing content and identifies gaps
  - Campaign Designer - Helps design and plan marketing campaigns
  - SEO Optimizer - Provides SEO optimization recommendations
  - Component Populator - Generates content for page components

- 💬 **Conversational Interface** - Natural language interaction with streaming responses
- 🔄 **Context Awareness** - Maintains conversation context across pages
- 📊 **Analytics Tracking** - Tracks token usage, MCP calls, and user actions
- 🎯 **Intent Re-classification** - Automatically switches assistants mid-conversation
- 💾 **Persistent Conversations** - Stores conversation history by user and site

## Tech Stack

- **Frontend**: Next.js 15 (App Router), React, TypeScript, Tailwind CSS
- **Backend**: Next.js API Routes, OpenAI GPT-4
- **Database**: PostgreSQL (Vercel Postgres), Prisma ORM
- **MCP Integration**: @markstiles/sitecore-search-mcp (deployed on Railway)
- **Deployment**: Vercel (Next.js app), Railway (MCP server)

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials. For local Supabase Postgres (via `docker/docker-compose.yml`):

```env
POSTGRES_URL="postgresql://postgres:postgres_dev_password_change_me@localhost:5432/postgres?schema=public"
POSTGRES_PRISMA_URL="postgresql://postgres:postgres_dev_password_change_me@localhost:5432/postgres?schema=public&pgbouncer=true"
POSTGRES_URL_NON_POOLING="postgresql://postgres:postgres_dev_password_change_me@localhost:5432/postgres?schema=public"
DATABASE_URL="postgresql://postgres:postgres_dev_password_change_me@localhost:5432/postgres?schema=public"

# OpenAI
OPENAI_API_KEY="sk-..."

# MCP Server (Railway URL after deployment)
MCP_SERVER_URL="ws://your-railway-app.railway.app"

# Sitecore
SITECORE_DOMAIN_ID="12345678"
SITECORE_CLIENT_KEY="123456789-12345678"
SITECORE_API_KEY="01-xxxxxxxx..."
```

### 3. Start Supabase Postgres (optional local dev)

```bash
cd ../docker
docker-compose up -d
```

### 4. Set up Database

```bash
npm run db:setup
```

### 4. Deploy MCP Server to Railway

Navigate to `../railway-mcp-server/` folder and follow the README instructions.

### 5. Run Development Server

```bash
npm run dev
```

Visit `http://localhost:3000/editor-panel` to see the chatbot interface.

## Deployment

### Deploy Next.js App to Vercel

```bash
vercel
```

Configure environment variables in Vercel dashboard.

### Deploy MCP Server to Railway

See `../railway-mcp-server/README.md` for detailed instructions.

## Usage

### Starting a Conversation

1. Open the chatbot panel in XM Cloud Pages Editor
2. Type your question or request
3. The system automatically classifies your intent and selects the appropriate assistant

### Assistant Types

- **Content Auditor**: "Audit the blog section" or "Find content gaps"
- **Campaign Designer**: "Design a spring campaign" or "Create a promotion"
- **SEO Optimizer**: "Optimize this page for SEO" or "Suggest keywords"
- **Component Populator**: "Fill this hero banner" or "Generate CTA text"

## Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation.

## Learn More

- [Next.js Documentation](https://nextjs.org/docs)
- [Sitecore XM Cloud](https://doc.sitecore.com)
- [MCP Protocol](https://modelcontextprotocol.io)
