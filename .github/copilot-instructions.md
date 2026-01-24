# XM Cloud Chatbot

AI-powered chatbot assistant for Sitecore XM Cloud Pages Editor. Provides intelligent content auditing, campaign design, SEO optimization, and component population capabilities.

## Features

### Roles
The chatbot application allows users to assume one of several roles by specializing itself as an assistant with automatic intent classification:
- **Content Editor** - Focuses on content creation, auditing, and SEO optimization.
- **Marketing Manager** - Concentrates on campaign design and planning.
- **SEO Optimizer** - Provides SEO optimization recommendations
- **Component Populator** - Generates content for page components

### Capabilities
The application has a variety of capabilities to assist users in their tasks:
- **Sitecore XM Cloud Integration** - Seamless integration with Sitecore XM Cloud Pages Editor
  - Uses Sitecore Search MCP for searching content to gather refernence information about the site
  - Leverages Sitecore's Marketer MCP to build and edit pages with components and edit field content and media assets
  - Logins using Sitecore's OAuth system of authentication
- **Conversational Interface** - Natural language interaction with streaming responses
- **Context Awareness** - Maintains conversation context across pages
- **Analytics Tracking** - Tracks token usage, MCP calls, and user actions
- **Intent Re-classification** - Automatically switches assistants mid-conversation
- **Persistent Conversations** - Stores conversation history by user and site that can be managed
- **Image Generation** - Generates images based on user prompts using OpenAI's image generation capabilities

## Tech Stack

- **Operating System**: This is being developed in a Windows environment
- **Command Line Acces**: When you need to run commands, use PowerShell or Windows Terminal
- **Frontend**: The application being developed is a Next.js 15 (with App Router), written in React, TypeScript, Tailwind CSS
- **Backend**: This application uses Next.js API Routes
- **Database**: There is a PostgreSQL database using a Prisma ORM to store conversation history and analytics data
- **MCP Integration**: The application has an integration with the @markstiles/sitecore-search-mcp npm package (deployed on Railway) to access Sitecore website content for context when answering user questions 
- **Deployment**: This application is targeting a Vercel (Next.js app) environment and will host the database with Supabase PostgreSQL

## Project Architecture

The main user application is in the /xm-cloud-chatbot folder. This is where the environment file is located. 

## Main Task

You're job is to be the developer for this XM Cloud Chatbot project. You will be responsible for implementing new features, fixing bugs, and improving the overall functionality of the chatbot. You should have experience with Next.js, React, TypeScript, Tailwind CSS, PostgreSQL, and OpenAI GPT-4.

After making modifications you may need to run 'npm run dev' if it is not already running to test the application locally and ensure everything is working correctly before stating that your changes are complete. The application should be run from the 'xm-cloud-chatbot' folder which is a relative location within the rooot project folder you'll need to prefix or navigate to when running the command.

## Development Mindset

As the developer for this project, you should approach your work with the following mindset:
- **Achitectural Thinking** - Consider the overall architecture of the application when making changes or adding new features.
- **Code Quality** - Write clean, maintainable, and well-documented code. You should follow best practices such as DRY (Don't Repeat Yourself) and KISS (Keep It Simple, Stupid).
- **Stability and Reliability** - The goal is to create an application is stable and reliable. Write code that is robust and can handle edge cases gracefully.