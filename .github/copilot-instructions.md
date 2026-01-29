# XM Cloud Chatbot

AI-powered chatbot assistant for Sitecore XM Cloud Pages Editor. Provides intelligent content auditing, campaign design, SEO optimization, and component population capabilities. By integrating into the Pages Editor, the chatbot offers context-aware assistance, automatic role specialization based on user intent, and the ability to work with Sitecore without requiring deep technical knowledge.

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
- **Document Analysis** - Allows users to upload `.docx`, `.pdf`, `.txt`, and `.md` files. The system extracts the content (XML-to-HTML for docx, text extraction for others), and injects it into the context for the AI to analyze. The UI collapses this large content by default using `<details>` tags.

## Tech Stack

- **Operating System**: This is being developed in a Windows environment
- **Command Line Acces**: When you need to run commands on the command line, use PowerShell or Windows Terminal. For example, grep or grep_search is not available, so use Select-String instead.
- **Directory Scope (CRITICAL)**: This is a nested project. The root folder `MultimodalMarketingDemo` is just a container. The actual Next.js application lives in `xm-cloud-chatbot`. ALL npm commands (install, run, build) MUST be run from inside `xm-cloud-chatbot`. Running `npm install` in the root will create a phantom `package.json` that breaks module resolution (e.g. `Can't resolve 'tailwindcss'`). Always check `Get-Location` before installing.
- **Frontend**: The application being developed is a Next.js 15 (with App Router), written in React, TypeScript, Tailwind CSS
- **Backend**: This application uses Next.js API Routes. It uses `adm-zip` and `fast-xml-parser` for handling .docx file uploads server-side.
- **Components**: The Chat UI uses `rehype-raw` to safely render specific HTML tags (like `<details>`) inside markdown.
- **Database**: There is a PostgreSQL database using a Prisma ORM to store conversation history and analytics data
- **Deployment**: This application is targeting a Vercel (Next.js app) environment and will host the database with Supabase PostgreSQL

## Project Architecture

The main user application is in the /xm-cloud-chatbot folder. This is where the environment file is located. 

### Templates

There are a set of instruction templates located in the /lib/prompts/templates.ts file. These are the instructions that the in application model will use to define the role it will assume when assisting the user. This should not be confused with the .github/copilot-instructions.md file which contains instructions for GitHub Copilot to assist in writing code for the project itself. You should assume updating instructions is for the in application model unless otherwise specified.

## Main Task

You're job is to be the developer for this XM Cloud Chatbot project. You will be responsible for implementing new features, fixing bugs, and improving the overall functionality of the chatbot. You should have experience with Next.js, React, TypeScript, Tailwind CSS, PostgreSQL, and OpenAI GPT-4.

After making modifications you may need to run 'npm run dev' if it is not already running to test the application locally and ensure everything is working correctly before stating that your changes are complete. The application should be run from the 'xm-cloud-chatbot' folder which is a relative location within the rooot project folder you'll need to prefix or navigate to when running the command.

## Development Mindset

As the developer for this project, you should approach your work with the following mindset:
- **Achitectural Thinking** - Consider the overall architecture of the application when making changes or adding new features.
- **Code Quality** - Write clean, maintainable, and well-documented code. You should follow best practices such as DRY (Don't Repeat Yourself) and KISS (Keep It Simple, Stupid).
- **Stability and Reliability** - The goal is to create an application is stable and reliable. Write code that is robust and can handle edge cases gracefully.
- **Reuse over Reinvention** - Before implementing a new feature or functionality, check if there are existing libraries or components that can be reused. Code reuse should be abstracted to functions for future implementations.
- **Cause and Effect** - Solutions may not be obvious. Always try to understand the root cause of an issue rather than just addressing the symptoms. You should be able to reason about how different parts of the application interact and how changes in one area may affect others. Additionally, there may be other contextual influences on a problem that may not be directly connected but in a runtime scenario may be causing the issue or state based issues such as changes made during the operation of the application. Other causes may be latent and need to be uncovered through careful analysis.
- **MCP Priority** - When implementing functionality, always prioritize using Sitecore Marketer MCP tools if they exist for the task. Local implementation should be a fallback.
- **Smart Token Strategy** - When using the Agent API (`/stream/ai-agent-api`) locally (fallback), you MUST use the `getSmartToken` helper logic: prefer a Service Token (Client Credentials), and fall back gracefully to the User Token (Context/DB).

## Coding Standards

When you're quoting text inside instructions don't use backticks. Just use normal single quotes to denote code or string values. This is crucial because many instructions are embedded in template literals (backticked strings) in the code, and using unescaped backticks will break the syntax.

Don't rely on the proces.env.NODE_ENV variable to determine if you are in development mode. Instead, use a dedicated environment variable when needed. This makes it less dependent on Next and only on your own configuration.

Do not hard code specific rules for development vs production modes. Always use environment variables to control behavior so that it can be adjusted without code changes. You should prefer to make functions small and modular so that behavior can be composed as needed based on configuration.

I don't want hardcoded exceptions. I want general rules that handle more than a single case. 

## Instructions for Specific Scenarios

Instructions should always abstract values using <example-value> or {example-value} notation to indicate that these are variables that need to be resolved in context. Never hardcode specific values unless they are truly constants that never change.

### API Architecture and Authentication (CRITICAL)

The Sitecore XM Cloud ecosystem has a complex API topology with distinct authentication requirements. You must understand the "Split Routing" strategy to successfully interact with it.

#### 1. The Three Gateways
There are three main API gateways, each with different security rules:
*   **Authoring API (`xmapps-api`)**: Standard CMS operations. Accepts **User Tokens** (Auth0).
*   **Authoring GraphQL (`/authoring/graphql`)**: Flexible data queries. Accepts **User Tokens** (Auth0).
*   **Agent API Proxy (`/stream/ai-agent-api`)**: Specialized for AI agents. Strictly requires **Service Tokens** (Client Credentials) or User Tokens with specific "Automation" audience claims.

#### 2. The Token Trap
*   **User Tokens**: Obtained via interactive login (Auth0). They work great for `xmapps-api` and GraphQL but get rejected by the Agent API Proxy with `404 Failed to extract claims`.
*   **Service Tokens**: Obtained via `client_credentials` flow using an **Automation Client**. These work with the Agent API but require separate credentials.

#### 3. Configuration Requirements
To support full functionality, the project requires two sets of credentials in `.env`:
*   `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET`: For User Login (UI).
*   `SITECORE_AGENT_API_CLIENT_ID` / `SITECORE_AGENT_API_CLIENT_SECRET`: A dedicated **Automation Client** for backend service calls.

#### 4. Implementation Strategy (Split Routing)
Do not force all traffic through a single proxy.
*   **For Content Editing/Navigating (User Actions)**: Use the **User Token** and target the **Authoring API** or **GraphQL**.
    *   *Example*: Listing page children, creating pages, moving items.
    *   *Why*: The user context is required, and the Agent Proxy usually rejects these tokens.
*   **For Search/Analysis (System Actions)**: Use the **Service Token** and target the **Agent API**.
    *   *Example*: `getAllPagesForSite`, `search_site`, `getComponentsOnPage`.
    *   *Why*: These are heavy reads optimized for the Agent API.
*   **Resiliency Pattern**: If an Agent API call fails with a "Claims" error (404/401), catch it and fallback to the Authoring API or User Token if possible, logging the warning clearly.

### Errors

when attempting to fix errors, writing code that handles single cases like hardcoding responses or trying to create instructions that only work for one specific error is not acceptable. You should always aim to write code that is generic and can handle a variety of cases. This may involve creating utility functions, using polymorphism, or other techniques to make your code more flexible. You also do not want to generate instructions that indicate the chat app should not try to do specific functionality again. Instead, you want to make the code more robust so that it can handle those cases in the future without failing. This entails trying to understand the problem that underlies the error and addressing that root cause rather than just the symptom. 

### Notebook Construction
When creating or editing a Jupyter Notebook, follow these structural guidelines for better organization and maintainability:

1.  **Imports**: Always place all library references and imports in their own dedicated section at the top of the notebook.
2.  **Environment Variables**: Consolidate all environment variables and configuration settings into a dedicated "Variables" or "Configuration" section immediately following the imports. This keeps setup clean.
3.  **Functions**: Define each function in its own separate cell. This allows for individual updates and re-execution of specific logic without rerunning the entire notebook.
4.  **Experiment Configuration**: Place experiment names and run-specific configurations (like dynamic run names) in the cell where the run is actually initiated (e.g., the `if __main__` block or the final execution cell). This keeps execution parameters close to the action.

## Sitecore Marketer MCP
The chatbot uses the Sitecore Marketer MCP API to interact with Sitecore XM Cloud. This should be preferred whenever possible for operations that are supported by the MCP tools. Fall back to direct API calls only when necessary or the MCP does not support the required operation.
*   **Purpose**: These are high-level abstracted tools provided by the Marketer MCP server.
*   **Infrastructure**: These tools run via the MCP Protocol and connect to the configured MCP Server (default: `marketer-mcp-prod`).

### Available Tools
Below is a list of the tools and description of each tool that can be used to interact with Sitecore XM Cloud through the Marketer MCP API:

- add_component_on_page: Add component to a page
- add_language_to_page: Add a language to a page
- create_child_item: Create child item under parent
- create_component_datasource: Creaet component datasource
- create_content_item: Create content item
- create_page: Create a new page
- create_personalization_version: Create personalization version for a page
- delete_child_item: Delete child item
- delete_content: Delete content item
- get_all_languages: Get all available languages in the system
- get_all_pages_by_site: Get all pages by site
- get_allowed_components_by_placeholder: Get allowed components by placeholder
- get_asset_information: Get asset information by ID
- get_component: Get component details
- get_components_by_placeholder: Get placeholder components
- get_components_on_page: Get all components on a page
- get_content_item_by_id: Get content item by ID
- get_content_item_by_path: Get content item by path
- get_page: Get page details by ID and language
- get_page_html: Get page HTML content
- get_page_path_by_live_url: Get page path by live URL
- get_page_preview_url: Get the preview URL for a specific page
- get_page_screenshot: Get a screenshot of a page
- get_page_template_by_id: Get page template by id including available fields
- get_personalization_condition_template_by_id: Get personalization condition template by ID
- get_personalization_condition_templates: Get available personalization condition templates 
- get_personalization_versions_by_page: Get all personalization versions for a page
- get_site_id_from_item: Get site ID from item
- get_site_information: Get site information by site ID
- list_available_insertoptions: List available insert options for an item
- list_components: List all components for a site
- list_sites: List all sites with name and target hostname
- move_component_within_placeholder: Move component within placeholder
- remove_component_on_page: Remove component from page
- search_assets: Search assets by name, type, or tags
- search_component_datasources: Search component datasources
- search_site: Search site pages by title
- set_component_datasource: Set datasource for a component on a page
- update_asset: Update asset metadata and fields
- update_content: Update content item
- update_fields_on_content_item: Update fields on content item
- upload_asset: Upload new asset to media library

## NPM Libraries
These are the official Sitecore XM Cloud Client library for interacting with Sitecore XM Cloud APIs.
*   **WARNING**: By default, these libraries target the standard Authoring API. If `EDGE_PLATFORM_PROXY_URL` is set, they target the Proxy.
*   **Authentication**: If using the Agent Proxy (`edge-platform.sitecorecloud.io/stream/ai-agent-api`), these libraries will fail if passed a User Token. You MUST manage this distinction carefully or wrapper functions will break.

### client.agent
*   **Target**: Optimized for use with the **Agent API** (`/stream/ai-agent-api`).
*   **Auth**: Requires **Service Token** (Automation Client).

- sitesGetSitesList: Retrieves a list of all available sites with their basic information and configuration.
- sitesGetSiteDetails: Retrieves detailed information about a specific site including its configuration, themes, and available languages.
- sitesGetAllPagesBySite: Returns a flat list of routes for the specified site and language, each with id and path.
- sitesGetSiteIdFromItem: Returns the site root item ID for a given item by traversing ancestors to find the site root template
- pagesCreatePage: Creates a new page in the specified location with the given template, fields, and language. The page is created as a child of the specified parent page.
- pagesAddLanguageToPage: Creates a language version of an existing page. This allows you to have the same page content available in multiple languages.
- pagesGetComponentsOnPage: Retrieves a list of components that are currently added to a specific page.
- pagesAddComponentOnPage: Adds a component to a specific placeholder on a page. You can optionally specify a datasource for the component or create a new one.
- pagesSetComponentDatasource: Set component datasource
- pagesSearchSite: Searches all pages in a specific site by title or content. The response returns the matching pages with their details including id, path, display_name, and search_fields.
- pagesGetPagePathByLiveUrl: Get the page item path corresponding to a live URL. You can use this endpoint to find the page item that corresponds to a specific live URL on your website.
- pagesGetPageScreenshot: Captures and returns a screenshot of the specified page. This endpoint takes a screenshot of the live page and returns it as a base64-encoded image.
- pagesGetPageHtml: Retrieves the HTML content of a specific page. This endpoint returns the raw HTML of the page as it would appear in the browser.
- pagesGetPagePreviewUrl: Retrieves the preview URL of a specific page. This endpoint returns the URL that can be used to preview the page.
- pagesGetPageTemplateById: Retrieves detailed information about a specific page template, including its fields and settings. Use this endpoint to understand the structure and available fields of a template before creating pages.
- pagesGetPage: Retrieves comprehensive information about a page including its layout, components, placeholders, and available actions. This endpoint provides all the information needed to - understand and modify a page.
- pagesGetAllowedComponentsByPlaceholder: Retrieves a list of components that are allowed to be added to a specific placeholder on a page. This helps ensure only compatible components are added to each placeholder. You can use * to fetch all components.
- contentCreateContentItem: Creates a new content item with the specified template, fields, and location.
- contentDeleteContent: Deletes a content item and optionally all its child items.
- contentGetContentItemById: Retrieves detailed information about a specific content item using its unique identifier.
- contentUpdateContent: Updates comprehensive information about a content item including its fields and metadata.
- contentGetContentItemByPath: Retrieves detailed information about a content item using its path in the content tree.
- contentListAvailableInsertoptions: Retrieves the available content templates that can be inserted as child items under the specified parent item.
- componentsCreateComponentDatasource: Creates a new datasource item for a specific component with the provided field values. The datasource will be created in the appropriate location based on the component's configuration.
- componentsSearchComponentDatasources: Searches for available datasources that can be used with a specific component. This helps find existing content items that can serve as datasources.
- componentsListComponents: Retrieves a list of all available components for a specific site. This includes both built-in components and custom components that can be used in pages.
- componentsGetComponent: Retrieves detailed information about a specific component including its fields, datasource requirements, and configuration options.
- assetsUploadAsset: Uploads a new digital asset to the system. The asset will be processed and stored in the specified location with the provided metadata.
- assetsSearchAssets: Searches for digital assets based on query terms, file types, or tags. Returns a list of matching assets with their metadata and download URLs.
- assetsGetAssetInformation: Retrieves detailed information about a specific digital asset including its metadata, file properties, and usage information.
- assetsUpdateAsset: Updates the metadata and properties of an existing digital asset. This allows you to modify asset information such as alt text, titles, and custom field values.
- environmentsListLanguages: Retrieves all languages available.
- personalizationCreatePersonalizationVersion: Creates a new personalization definition with one or more variants.
- personalizationGetPersonalizationVersionsByPage: Retrieves all personalization versions configured for a specific page, including their targeting rules and content variations.
- personalizationGetConditionTemplates: Retrieves all available condition templates for personalization.
- personalizationGetConditionTemplateById: Returns a condition template by ID and its parameters for creating a personalization variant on a page
- jobsRevertJob: Reverts the operations of the specified job.
- jobsGetJob: Retrieves the details of the specified job.
- jobsListOperations: Retrieves the operations associated with the specified job.

### client.authoring
*   **Target**: The Standard **Authoring API** (`xmapps-api`).
*   **Auth**: Accepts **User Tokens** (Auth0).

- graphql: Send a GraphQL query or mutation request to the Sitecore Authoring API. Both queries and mutations are supported.

### client.content
*   **Target**: The **Delivery/Preview GraphQL API**.
*   **Auth**: Accepts User Tokens or API Keys.

- graphql: Send a GraphQL query request to the Sitecore GraphQL API. Mutations are not supported by the Preview API and Delivery API.

### client.content-transfer (Advanced)
*   **Target**: Specialized endpoints for migration.

- createContentTransfer: Creates a new transfer in the Source environment.
- getContentTransferStatus: Gets the status of the created content transfer by transfer ID.
- getChunk: Retrieves the specified chunk from the specified chunk set in the Source environment.
- saveChunk: Saves the specified chunk from the specified chunk set in the Target environment.
- completeChunkSetTransfer: Marks the specified chunk set as complete for the given transfer.
- deleteContentTransfer: Deletes the content transfer by transfer ID. Starts a clean-up of all resources related to content transfer in Source or Target environments.
- consumeFile: Starts consuming a `.raif` file in the specified database.
- getBlobState: Retrieves the status of a consumed `.raif` file.

### client.pages
*   **Target**: The **Pages Editor API** (Subset of Authoring).
*   **Auth**: Accepts **User Tokens**.

- deletePage: Deletes a page.
- retrievePage: Fetches information about a page (including statistics, template, layout, publishing and workflow information).
- updateFields: Updates values of existing fields for a specific page.
- retrievePageState: Fetches basic information about a page (identifier, display name and revision) and optionally workflow, layout and version data.
- search: Fetches a list of pages and folders whose name or display name match the search criteria, while applying filters and language options.
- retrieveInsertOptions: Fetches the list of possible templates which are compatible insert options for a page.
- retrievePageVersions: Fetches the list of page versions.
- addPageVersions: Creates a new version of a page.
- listPageVariants: * Fetches the identifiers of currently active personalization variants for a page.
- getLivePageState: Checks if the requested page is published to Edge.
- createPage: Creates a new page.
- saveLayout: Updates the layout of a page.
- saveFields: Updates the fields of a page.
- duplicatePage: Creates a copy of a page.
- renamePage: Changes the name of a page.
- addPageVersion: Creates a new version of a page.
- deletePageVersions: Deletes the specified version of a page.

### client.sites
*   **Target**: The **Sites Management API** (Subset of Authoring).
*   **Auth**: Accepts **User Tokens** (except when routed via Proxy to Agent API).

- listLanguages: Retrieves the list of languages added to the environment.
- createLanguage: Adds a language to your environment to create content in that language, You must provide the language code. You can optionally input region code and spell checker. You choose from the languages supported by Sitecore XM Cloud. If you do not know the language code of the language, first retrieve the list of languages supported in Sitecore XM Cloud. 
- listSupportedLanguages: Retrieves the list of languages supported by Sitecore XM Cloud, and associated data.
- listCollections: Fetches the list of site collections in the environment, with associated details.
- createCollection: Creates a collection by specifying a name and, optionally, a display name and description.
- deleteCollection: Deletes a site collection, including sites in that collection.
- retrieveCollection: Fetches information about a site collection.
- updateCollection: Updates the display name and the description of the site collection. To change the system name of a collection, see rename a site collection.
- getFavoriteSites: Fetches a list of your favorite sites
- addFavoriteSite:  Adds a site to your list of favorites
- getFavoriteSiteTemplates: Fetches a list of your favorite site templates
- addFavoriteSiteTemplate: Adds a site template to your list of favorites
- listJobs: Fetches information about background jobs. Returns empty array if no jobs are running.
- retrieveJob: Fetches information about a background job.
- aggregateLivePageVariants: Returns currently active personalization variants for the requested pages.
- aggregatePageData: Aggregates data about multiple pages and their components.
- renameCollection: Changes the system name of a site collection.
- sortCollections: By assigning a sort value to site collection IDs, you can use this endpoint to apply an order by which collections are sorted in the Sites user interface and in Content Editor. validateCollectionName: Validates a site collection name to ensure it meets the required criteria. The validations applied to the collection name: Is a string and can't be null, Is unique, The length of the name is a maximum of 50 characters, Can't start or end with a space, Can't start with a dash, Can include Latin alphanumeric characters, spaces and dashes. The lower the sort value, the higher the site appears in the interface.
- deleteLanguage: Deletes a language from the XM Cloud environment. To delete a language from the system, you must provide the regional ISO code of the language. If you do not know the ISO code of the language, first retrieve the list of languages added to the environment.
- updateLanguage: Updates a language supported by Sitecore XM Cloud. To update a language, you must provide the regional ISO code of the language. If you do not know the ISO code of the language, first retrieve the list of languages supported in Sitecore XM Cloud.
- removeFavoriteSite: Removes a site from your list of favorites
- removeFavoriteSiteTemplate: Removes a site template from your list of favorites
- listSites: Fetches the list of sites in the environment, with associated details.
- createSite: Creates a site for the environment. Sites are created using site templates. Every site belongs to a site collection. You can either create a site inside an existing collection or create a new one. It is also possible to create a site by duplicating a site.
- deleteSite: Deletes a site, including its pages, settings, media files, data sources, presentation elements, dictionaries, components, variants, and page designs. Everyone in the environment will lose access to the deleted site. Deleting a site affects related websites in the collection: If the site shares items with other sites, this might result in broken links, Items that are cloned to other sites are turned into regular items, and the links removed.
- retrieveSite: Fetches information about a site.
- updateSite: Updates various parameters of a site. To change the name of a site, see rename a site
- copySite: You can create a site by duplicating an existing one. When you duplicate a site, its content items (such as pages and images, folder structure, and links) are copied. Most of the settings are also copied, but you can change those later. The new site's path parameters and response body schema will be the same as the original site.
- renameSite: Changes the system name of a site.
- sortSites: By assigning a sort value to site IDs, you can use this endpoint to apply an order by which sites are sorted in the Sites user interface and in Content Editor. The lower the sort value, the higher the site appears in the interface.
- validateSiteName: Validates a site name to ensure it meets the required criteria. The validations applied to the site name: Is a string and can't be null, Is unique, The length of the name is a maximum of 50 characters, Can't start or end with a space, Can't start with a dash, Can include Latin alphanumeric characters, spaces and dashes.
- listTrackedSites: Fetches a list of sites that use an analytics identifier
- listCollectionSites: Fetches a list of sites in a site collection.
- detachAnalyticsIdentifier: Removes the analytics identifiers from one or more sites.
- retrieveSiteHierarchy: Fetches hierarchy information about the main page of a site, including its children, ancestors, and siblings.
- retrievePageHierarchy: Fetches hierarchy information about a page, including its children, ancestors, and siblings.
- listPageAncestors: Fetches information about the ancestors of a page.
- listPageChildren: Fetches information about the children of a page.
- listHosts: Retrieves the list of hosts for a site.
- createHost: Creates a host for a site.
- deleteHost: Deletes a site using a hostID. Deletes a site, including its pages, settings, media files, data sources, presentation elements, dictionaries, components, variants, and page designs. Everyone in the environment will lose access to the deleted site.
- retrieveHost: Fetches details about a site host.
- updateHost: Modifies the properties of a host.
- getRenderingHosts: Fetches a list of rendering hosts for a site.
- listSiteTemplates: Gets the site templates available in the environment that can be used for creating sites. Learn more about site templates
- uploadSiteThumbnail: Uploads an image to be used as thumbnail for a site when it is displayed in the XM Cloud Sites application
- retrieveLocalizationStatistics: Fetches localization statistics for a site, including the number of pages in each locale.
- retrieveSitemapConfiguration: Fetches a sitemap
- updateSitemapConfiguration: Updates a sitemap
- retrieveWorkflowStatistics: Fetches the workflows defined for a site, their states, and the number of pages in each state