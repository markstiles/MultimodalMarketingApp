// TypeScript types for XM Cloud Editor messages

export interface EditorContext {
  pageId: string;
  siteName: string;
  siteId: string;
  userId: string;
  selectedComponentId?: string;
  pagePath?: string;
  language?: string;
}

export interface EditorMessage {
  type: 'context' | 'component_selected' | 'page_changed' | 'ready';
  data: EditorContext | Record<string, unknown>;
  origin: string;
}

export interface ChatbotMessage {
  type: 'update_component' | 'navigate_to_page' | 'request_context';
  data: UpdateComponentData | NavigateData | Record<string, never>;
}

export interface UpdateComponentData {
  componentId: string;
  field: string;
  value: string;
}

export interface NavigateData {
  pageId: string;
}

export function isValidEditorOrigin(origin: string): boolean {
  // Add your XM Cloud domain patterns here
  const allowedOrigins = [
    'https://pages.sitecorecloud.io',
    'https://xmc-*.sitecorecloud.io',
    /^https:\/\/.*\.sitecorecloud\.io$/,
  ];

  // For development
  if (process.env.NODE_ENV === 'development') {
    allowedOrigins.push('http://localhost:3000', 'http://localhost:3001');
  }

  return allowedOrigins.some((pattern) => {
    if (typeof pattern === 'string') {
      return origin === pattern || origin.startsWith(pattern);
    }
    return pattern.test(origin);
  });
}
