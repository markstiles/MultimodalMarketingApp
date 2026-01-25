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

export const GET_PAGE_COMPONENTS_TOOL = {
  type: 'function' as const,
  function: {
    name: 'get_page_components',
    description: 'Get all components on a specific page. Returns component names, IDs, and placeholders. Use this when the user asks about components on a page.',
    parameters: {
      type: 'object',
      properties: {
        pageId: {
          type: 'string',
          description: 'The ID of the page to get components for. If omitted, uses the current page context.',
        },
        language: {
          type: 'string',
          description: 'The language to get components for (e.g., "en"). Defaults to current context language.',
        },
      },
      required: [],
    },
  },
};

export const GET_ALLOWED_COMPONENTS_TOOL = {
  type: 'function' as const,
  function: {
    name: 'get_allowed_components',
    description: 'Get allowed components for a specific placeholder on a page. Use this when the user asks what components can be added to a placeholder.',
    parameters: {
      type: 'object',
      properties: {
        pageId: {
          type: 'string',
          description: 'The ID of the page.',
        },
        placeholderName: {
          type: 'string',
          description: 'The name of the placeholder (e.g. "headless-main", "jss-main").',
        },
        language: {
          type: 'string',
          description: 'The language code (default: en).',
        },
      },
      required: ['placeholderName'],
    },
  },
};

export const GET_PAGE_TOOL = {
  type: 'function' as const,
  function: {
    name: 'get_page',
    description: 'Get high-level metadata about a page by ID.',
    parameters: {
      type: 'object',
      properties: {
        pageId: {
          type: 'string',
          description: 'The ID of the page.',
        },
        language: {
          type: 'string',
          description: 'The language code (default: en).',
        },
      },
      required: ['pageId'],
    },
  },
};

export const GET_PAGE_HTML_TOOL = {
  type: 'function' as const,
  function: {
    name: 'get_page_html',
    description: 'Get the rendered HTML of a page. Use this for analyzing content, SEO, or layout structure.',
    parameters: {
      type: 'object',
      properties: {
        pageId: {
          type: 'string',
          description: 'The ID of the page.',
        },
        language: {
          type: 'string',
          description: 'The language code (default: en).',
        },
      },
      required: ['pageId'],
    },
  },
};

export const GET_PATH_BY_URL_TOOL = {
  type: 'function' as const,
  function: {
    name: 'get_path_by_url',
    description: 'Resolve a live website URL to an internal Sitecore item path and ID.',
    parameters: {
      type: 'object',
      properties: {
        url: {
          type: 'string',
          description: 'The full URL to resolve.',
        },
      },
      required: ['url'],
    },
  },
};

export const LIST_COMPONENTS_TOOL = {
  type: 'function' as const,
  function: {
    name: 'list_components',
    description: 'List all available components in the library for a specific site. Returns component names and IDs.',
    parameters: {
      type: 'object',
      properties: {
        siteName: {
          type: 'string',
          description: 'The name of the site.',
        },
      },
      required: ['siteName'],
    },
  },
};

export const GET_COMPONENT_TOOL = {
  type: 'function' as const,
  function: {
    name: 'get_component',
    description: 'Get details about a specific component, including its available fields and datasource requirements.',
    parameters: {
      type: 'object',
      properties: {
        componentName: {
          type: 'string',
          description: 'The name of the component (e.g. "ContentBlock", "Hero").',
        },
      },
      required: ['componentName'],
    },
  },
};

export const SEARCH_SITE_TOOL = {
  type: 'function' as const,
  function: {
    name: 'search_site',
    description: 'Search for pages in the site by keyword/query.',
    parameters: {
      type: 'object',
      properties: {
        siteName: {
          type: 'string',
          description: 'The name of the site.',
        },
        query: {
          type: 'string',
          description: 'Search keywords.',
        },
        language: {
          type: 'string',
          description: 'Language code (default: en).',
        },
      },
      required: ['siteName', 'query'],
    },
  },
};

// --- New Write Tools based on Agent/Pages/Sites API ---

export const ADD_COMPONENT_TOOL = {
  type: 'function' as const,
  function: {
    name: 'add_component_on_page',
    description: 'Add a new component to a placeholder on a page.',
    parameters: {
      type: 'object',
      properties: {
        pageId: { type: 'string', description: 'The ID of the page.' },
        componentName: { type: 'string', description: 'The name of the component to add (e.g., "Hero").' },
        placeholderName: { type: 'string', description: 'The placeholder key (e.g., "headless-main").' },
        language: { type: 'string', description: 'Language code (default: en).' }
      },
      required: ['pageId', 'componentName', 'placeholderName']
    }
  }
};

export const CREATE_PAGE_TOOL = {
  type: 'function' as const,
  function: {
    name: 'create_page',
    description: 'Create a new page under a parent item.',
    parameters: {
      type: 'object',
      properties: {
        parentId: { type: 'string', description: 'The ID of the parent item/page.' },
        templateId: { type: 'string', description: 'The ID of the page template to use.' },
        name: { type: 'string', description: 'The name of the new page (will be part of the URL).' },
        language: { type: 'string', description: 'Language code (default: en).' }
      },
      required: ['parentId', 'templateId', 'name']
    }
  }
};

export const CREATE_CONTENT_TOOL = {
  type: 'function' as const,
  function: {
    name: 'create_content_item',
    description: 'Create a new content item (non-page data) in the content tree.',
    parameters: {
      type: 'object',
      properties: {
        parentId: { type: 'string', description: 'The ID of the parent item/folder.' },
        templateId: { type: 'string', description: 'The ID of the data template.' },
        name: { type: 'string', description: 'The name of the new item.' },
        language: { type: 'string', description: 'Language code (default: en).' }
      },
      required: ['parentId', 'templateId', 'name']
    }
  }
};

export const UPDATE_CONTENT_TOOL = {
  type: 'function' as const,
  function: {
    name: 'update_content',
    description: 'Update fields on an existing content item or page.',
    parameters: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'The ID of the item to update.' },
        fields: { 
           type: 'object', 
           description: 'Key-value pairs of fields to update (e.g., { "Title": "New Title" }).' 
        },
        language: { type: 'string', description: 'Language code (default: en).' }
      },
      required: ['id', 'fields']
    }
  }
};

export const DELETE_CONTENT_TOOL = {
  type: 'function' as const,
  function: {
    name: 'delete_content',
    description: 'Delete a content item or page.',
    parameters: {
      type: 'object',
      properties: {
        itemId: { type: 'string', description: 'The ID of the item to delete.' }
      },
      required: ['itemId']
    }
  }
};

export const LIST_SITES_TOOL = {
    type: 'function' as const,
    function: {
      name: 'list_sites',
      description: 'List all sites in the current environment.',
      parameters: {
        type: 'object',
        properties: {},
        required: []
      }
    }
  };

export const LIST_SITE_COLLECTIONS_TOOL = {
    type: 'function' as const,
    function: {
        name: 'list_site_collections',
        description: 'List all site collections.',
        parameters: { type: 'object', properties: {}, required: [] }
    }
};

export const GET_FAVORITE_SITES_TOOL = {
    type: 'function' as const,
    function: {
        name: 'get_favorite_sites',
        description: 'Get the list of favorite sites for the user.',
        parameters: { type: 'object', properties: {}, required: [] }
    }
};

export const LIST_LANGUAGES_TOOL = {
    type: 'function' as const,
    function: {
        name: 'list_languages',
        description: 'List configured languages.',
        parameters: { type: 'object', properties: {}, required: [] }
    }
};

export const AGGREGATE_PAGE_DATA_TOOL = {
    type: 'function' as const,
    function: {
        name: 'aggregate_page_data',
        description: 'Aggregate data for a specific page (useful for exporting or analysis).',
        parameters: {
            type: 'object',
            properties: {
                siteId: { type: 'string', description: 'The ID of the site.' },
                pageId: { type: 'string', description: 'The ID of the page.' },
                language: { type: 'string', description: 'Language code.' }
            },
            required: ['siteId', 'pageId']
        }
    }
};

export const LIST_JOBS_TOOL = {
    type: 'function' as const,
    function: {
        name: 'list_jobs',
        description: 'List asynchronous jobs.',
        parameters: { type: 'object', properties: {}, required: [] }
    }
};

// --- Comprehensive Tool Expansion ---

export const SEARCH_ASSETS_TOOL = {
    type: 'function' as const,
    function: {
        name: 'search_assets',
        description: 'Search for assets in the media library.',
        parameters: {
            type: 'object',
            properties: {
                query: { type: 'string', description: 'The search query.' },
                language: { type: 'string', description: 'Language code (default: en).' }
            },
            required: ['query']
        }
    }
};

export const CREATE_COMPONENT_DATASOURCE_TOOL = {
    type: 'function' as const,
    function: {
        name: 'create_component_datasource',
        description: 'Create a new datasource item for a component.',
        parameters: {
            type: 'object',
            properties: {
                name: { type: 'string' },
                templateId: { type: 'string' },
                locationId: { type: 'string', description: 'Parent item ID where datasource should include.' },
                language: { type: 'string' }
            },
            required: ['name', 'templateId', 'locationId']
        }
    }
};

export const GET_PAGE_PREVIEW_URL_TOOL = {
    type: 'function' as const,
    function: {
        name: 'get_page_preview_url',
        description: 'Get the preview URL for a page.',
        parameters: {
            type: 'object',
            properties: {
                pageId: { type: 'string' },
                language: { type: 'string' }
            },
            required: ['pageId']
        }
    }
};

export const SET_COMPONENT_DATASOURCE_TOOL = {
    type: 'function' as const,
    function: {
        name: 'set_component_datasource',
        description: 'Assign a datasource to a component on a page.',
        parameters: {
            type: 'object',
            properties: {
                pageId: { type: 'string' },
                componentId: { type: 'string', description: 'The unique ID/UID of the component instance on the page.' },
                datasourceId: { type: 'string' },
                language: { type: 'string' }
            },
            required: ['pageId', 'componentId', 'datasourceId']
        }
    }
};

export const DUPLICATE_PAGE_TOOL = {
    type: 'function' as const,
    function: {
        name: 'duplicate_page',
        description: 'Duplicate an existing page.',
        parameters: {
            type: 'object',
            properties: {
                pageId: { type: 'string' },
                newName: { type: 'string' },
                language: { type: 'string' }
            },
            required: ['pageId', 'newName']
        }
    }
};

export const LIST_PAGE_CHILDREN_TOOL = {
    type: 'function' as const,
    function: {
        name: 'list_page_children',
        description: 'List the child items of a page/item.',
        parameters: {
            type: 'object',
            properties: {
                itemId: { type: 'string' },
                language: { type: 'string' }
            },
            required: ['itemId']
        }
    }
};


export const LIST_SITE_TEMPLATES_TOOL = {
    type: 'function' as const,
    function: {
        name: 'list_site_templates',
        description: 'List available templates for creating sites.',
        parameters: { type: 'object', properties: {}, required: [] }
    }
};

export const GET_RENDERING_HOSTS_TOOL = {
    type: 'function' as const,
    function: {
        name: 'get_rendering_hosts',
        description: 'Get configured rendering hosts.',
        parameters: { type: 'object', properties: {}, required: [] }
    }
};

export const LIST_PAGE_VERSIONS_TOOL = {
    type: 'function' as const,
    function: {
        name: 'list_page_versions',
        description: 'Retrieve versions of a page.',
        parameters: {
            type: 'object',
            properties: {
                pageId: { type: 'string' },
                language: { type: 'string' }
            },
            required: ['pageId']
        }
    }
};

export const GET_CONDITION_TEMPLATES_TOOL = {
    type: 'function' as const,
    function: {
        name: 'get_condition_templates',
        description: 'Get personalization condition templates.',
        parameters: {
            type: 'object',
            properties: { language: { type: 'string' } },
            required: []
        }
    }
};

export function getAllTools() {
  return [
    IMAGE_GENERATION_TOOL,
    ASSET_URL_TOOL,
    LIST_PAGES_TOOL,
    GET_PAGE_COMPONENTS_TOOL,
    GET_ALLOWED_COMPONENTS_TOOL,
    GET_PAGE_TOOL,
    GET_PAGE_HTML_TOOL,
    GET_PATH_BY_URL_TOOL,
    LIST_COMPONENTS_TOOL,
    GET_COMPONENT_TOOL,
    SEARCH_SITE_TOOL,
    ADD_COMPONENT_TOOL,
    CREATE_PAGE_TOOL,
    CREATE_CONTENT_TOOL,
    UPDATE_CONTENT_TOOL,
    DELETE_CONTENT_TOOL,
    LIST_SITES_TOOL,
    LIST_SITE_COLLECTIONS_TOOL,
    GET_FAVORITE_SITES_TOOL,
    LIST_LANGUAGES_TOOL,
    AGGREGATE_PAGE_DATA_TOOL,
    LIST_JOBS_TOOL,
    SEARCH_ASSETS_TOOL,
    CREATE_COMPONENT_DATASOURCE_TOOL,
    GET_PAGE_PREVIEW_URL_TOOL,
    SET_COMPONENT_DATASOURCE_TOOL,
    DUPLICATE_PAGE_TOOL,
    LIST_PAGE_CHILDREN_TOOL,
    LIST_SITE_TEMPLATES_TOOL,
    GET_RENDERING_HOSTS_TOOL,
    LIST_PAGE_VERSIONS_TOOL,
    GET_CONDITION_TEMPLATES_TOOL,
    ...CLIENT_ACTION_TOOLS
  ];
}




