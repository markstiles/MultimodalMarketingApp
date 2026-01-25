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
  - Uses Sitecore client and xmc npm package library to build and edit pages with components and edit field content and media assets
- **Conversational Interface** - Natural language interaction with streaming responses
- **Context Awareness** - Maintains conversation context across pages
- **Analytics Tracking** - Tracks token usage, api calls, and user actions
- **Intent Re-classification** - Automatically switches assistants mid-conversation
- **Persistent Conversations** - Stores conversation history by user and site that can be managed
- **Image Generation** - Generates images based on user prompts using OpenAI's image generation capabilities

## Tech Stack

- **Operating System**: This is being developed in a Windows environment
- **Command Line Acces**: When you need to run commands on the command line, use PowerShell or Windows Terminal
- **Frontend**: The application being developed is a Next.js 15 (with App Router), written in React, TypeScript, Tailwind CSS
- **Backend**: This application uses Next.js API Routes
- **Database**: There is a PostgreSQL database using a Prisma ORM to store conversation history and analytics data
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

## Coding Standards

When you're quoting text inside instructions don't use backticks. Just use normal single quotes to denote code or string values.

Don't rely on the proces.env.NODE_ENV variable to determine if you are in development mode. Instead, use a dedicated environment variable when needed. This makes it less dependent on Next and only on your own configuration.

Do not hard code specific rules for development vs production modes. Always use environment variables to control behavior so that it can be adjusted without code changes. You should prefer to make functions small and modular so that behavior can be composed as needed based on configuration.