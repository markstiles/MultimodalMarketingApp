// Hardcoded tool definitions for OpenAI function calling
// Based on @markstiles/sitecore-search-mcp available tools

export const SITECORE_SEARCH_TOOLS = [
  {
    type: 'function' as const,
    function: {
      name: 'sitecore_search_query',
      description: 'Execute a basic search query in Sitecore Search. Use this to find content across the site.',
      parameters: {
        type: 'object',
        properties: {
          fields: {
            type: 'array',
            items: { type: 'string' },
            description: 'Array of field names to return in search results (default: ["name", "description"])',
          },
          domainId: {
            type: 'string',
            description: 'Sitecore domain ID',
          },
          rfkId: {
            type: 'string',
            description: 'RFK widget ID for the search',
          },
          keyphrase: {
            type: 'string',
            description: 'Search query text (optional)',
          },
          entity: {
            type: 'string',
            description: 'Entity type to search (e.g., content, product, page)',
          },
          page: {
            type: 'number',
            description: 'Page number for pagination (default: 1)',
          },
          limit: {
            type: 'number',
            description: 'Results per page (default: 24)',
          },
        },
        required: ['fields', 'domainId', 'rfkId', 'entity'],
      },
    },
  },
  {
    type: 'function' as const,
    function: {
      name: 'sitecore_search_with_facets',
      description: 'Execute a faceted search with filtering and sorting capabilities. Use this for advanced searches with filters.',
      parameters: {
        type: 'object',
        properties: {
          fields: {
            type: 'array',
            items: { type: 'string' },
            description: 'Array of field names to return in search results (default: ["name", "description"])',
          },
          domainId: {
            type: 'string',
            description: 'Sitecore domain ID',
          },
          rfkId: {
            type: 'string',
            description: 'RFK widget ID for the search',
          },
          keyphrase: {
            type: 'string',
            description: 'Search query text',
          },
          facets: {
            type: 'array',
            description: 'Array of facet configurations with filters',
            items: {
              type: 'object',
              properties: {
                name: {
                  type: 'string',
                  description: 'Facet field name',
                },
                type: {
                  type: 'string',
                  description: 'Facet type (value or range)',
                },
                values: {
                  type: 'array',
                  items: { type: 'string' },
                  description: 'Filter values for this facet',
                },
              },
            },
          },
          sort: {
            type: 'object',
            description: 'Sort criteria (e.g., {price: "asc"})',
          },
        },
        required: ['fields', 'domainId', 'rfkId'],
      },
    },
  },
  {
    type: 'function' as const,
    function: {
      name: 'sitecore_ai_search',
      description: 'Get AI-powered answers to questions or generate related questions about content.',
      parameters: {
        type: 'object',
        properties: {
          fields: {
            type: 'array',
            items: { type: 'string' },
            description: 'Array of field names to return in search results (default: ["name", "description"])',
          },
          domainId: {
            type: 'string',
            description: 'Sitecore domain ID',
          },
          rfkId: {
            type: 'string',
            description: 'RFK widget ID',
          },
          keyphrase: {
            type: 'string',
            description: 'Search query or question',
          },
          type: {
            type: 'string',
            enum: ['answer', 'question'],
            description: 'Type of AI response: answer to query or related questions',
          },
          entity: {
            type: 'string',
            description: 'Entity type to search within',
          },
        },
        required: ['fields', 'domainId', 'rfkId', 'keyphrase', 'type'],
      },
    },
  },
];

export function getSitecoreSearchTools() {
  return SITECORE_SEARCH_TOOLS;
}

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
      'Generate a full Sitecore Edge asset URL (and optional thumbnail URL) from environmentHost + asset path/extension. Use this instead of guessing URLs.',
    parameters: {
      type: 'object',
      properties: {
        environmentHost: {
          type: 'string',
          description:
            'Environment-specific host segment (e.g., "xmc-...-dev..."). If omitted, the server default ENVIRONMENT_HOST is used.',
        },
        path: {
          type: 'string',
          description: 'Asset path under Edge, e.g. "/project/velir/site/first/my-image"',
        },
        extension: {
          type: 'string',
          description: 'Optional file extension (e.g., "png"). If path already has an extension, this is ignored.',
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

export function getAllTools() {
  return [...SITECORE_SEARCH_TOOLS, IMAGE_GENERATION_TOOL, ASSET_URL_TOOL];
}
