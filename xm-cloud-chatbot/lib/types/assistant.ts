// Assistant types and configurations

export type AssistantType = 
  | 'content_auditor'
  | 'campaign_designer'
  | 'seo_optimizer'
  | 'asset_manager'
  | 'content_authoring';

export interface AssistantConfig {
  type: AssistantType;
  name: string;
  description: string;
  systemPrompt: string;
  intentKeywords: string[];
  color: string;
  examplePrompts: string[];
}

export interface MCPTool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}
