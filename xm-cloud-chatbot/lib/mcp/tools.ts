// Hardcoded tool definitions for OpenAI function calling
// Based on @markstiles/sitecore-search-mcp available tools

// Image generation tool for OpenAI function calling
export const IMAGE_GENERATION_TOOL = {
  type: 'function' as const,
  function: {
    name: 'generate_image',
    description: 'Generate marketing-ready images from a concise prompt.',
    parameters: {
      type: 'object',
      properties: {
        prompt: {
          type: 'string',
          description: 'Detailed image description including subject, style, and composition.',
        },
        size: {
          type: 'string',
          enum: ['1024x1024', '1024x1792', '1792x1024'],
          description: 'Output resolution (default 1024x1024).',
        },
        n: {
          type: 'integer',
          minimum: 1,
          maximum: 4,
          description: 'Number of images to generate (default 1).',
        },
      },
      required: ['prompt'],
    },
  },
};

// Utility tool: generate Edge asset URLs for images/files
export const ASSET_URL_TOOL = {
  type: 'function' as const,
  function: {
    name: 'generate_asset_url',
    description:
      'Generate a full Sitecore media handler URL (and optional thumbnail URL) from environmentHost + assetId. Use this instead of guessing URLs.',
    parameters: {
      type: 'object',
      properties: {
        environmentHost: {
          type: 'string',
          description:
            'Environment-specific host segment (e.g., "xmc-...-dev..."). If omitted, the server default ENVIRONMENT_HOST is used.',
        },
        assetId: {
          type: 'string',
          description:
            'Asset item id (GUID). Accepts {GUID} or dashed GUID; it will be normalized to 32-hex "N format" for: https://<ENVIRONMENT_HOST>.sitecorecloud.io/sitecore/shell/Applications/-/media/<asset_id>.ashx',
        },
        explicitUrl: {
          type: 'string',
          description: 'If you already have a full http(s) URL, pass it here and it will be returned as-is.',
        },
        thumbnailWidth: {
          type: 'integer',
          description: 'If provided, also returns thumbUrl with ?w=<thumbnailWidth> (default 100).',
          minimum: 1,
          maximum: 2000,
        },
      },
      required: [],
    },
  },
};

export const CLIENT_CONTEXT_TOOLS = [
  {
    type: 'function' as const,
    function: {
      name: 'get_site_context',
      description: 'Get the extended site context (from client.query("site.context")). This provides more details than pages.context.',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
  },
  {
    type: 'function' as const,
    function: {
      name: 'get_application_context',
      description: 'Get the current host application context (from client.query("application.context")).',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
  },
  {
    type: 'function' as const,
    function: {
      name: 'get_pages_context',
      description: 'Get the current page context including site info and page info (from client.query("pages.context")).',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
  },
  {
    type: 'function' as const,
    function: {
      name: 'get_host_user',
      description: 'Get the current logged-in user information (from client.query("host.user")).',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
  },
];

export const CLIENT_ACTION_TOOLS = [
  {
    type: 'function' as const,
    function: {
      name: 'execute_client_mutation',
      description: 'Execute a client-side mutation via the Marketplace SDK. Use this for actions not covered by specific tools.',
      parameters: {
        type: 'object',
        properties: {
          mutation: {
            type: 'string',
            description: 'The mutation key (e.g., "pages.reloadCanvas")',
          },
          payload: {
            type: 'object',
            description: 'The mutation payload/arguments',
          },
        },
        required: ['mutation'],
      },
    },
  },
  {
    type: 'function' as const,
    function: {
      name: 'reload_page_canvas',
      description: 'Reload the page canvas in the editor. Use this when you have modified content and want the user to see the changes immediately.',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
  },
  {
    type: 'function' as const,
    function: {
      name: 'navigate_to_page',
      description: 'Navigate the user to a different page. CRITICAL: You MUST verify the valid Sitecore Item ID of the destination page using search or list_pages tools BEFORE calling this. Do not guess IDs.',
      parameters: {
        type: 'object',
        properties: {
          itemId: {
            type: 'string',
            description: 'The valid Sitecore Item ID (GUID) of the page to navigate to.',
          },
        },
        required: ['itemId'],
      },
    },
  },
];

export const LIST_PAGES_TOOL = {
  type: 'function' as const,
  function: {
    name: 'list_pages',
    description: 'List all pages in the current site. Returns a list of page names, IDs, and paths. Use this to find the ID of a page when the user asks to navigate to it by name.',
    parameters: {
      type: 'object',
      properties: {
        siteId: {
          type: 'string',
          description: 'The ID of the site to list pages for. If omitted, uses the current site context.',
        },
        language: {
          type: 'string',
          description: 'The language to list pages for (e.g., "en"). Defaults to current context language.',
        },
      },
      required: [],
    },
  },
};

export function getAllTools() {
  return [IMAGE_GENERATION_TOOL, ASSET_URL_TOOL, LIST_PAGES_TOOL, ...CLIENT_ACTION_TOOLS];
}
