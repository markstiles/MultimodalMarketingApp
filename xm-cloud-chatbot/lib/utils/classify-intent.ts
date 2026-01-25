import OpenAI from 'openai';
import { AssistantType } from '@/lib/types/assistant';
import { ASSISTANT_TEMPLATES, getDefaultAssistantType } from '@/lib/prompts/templates';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export interface IntentClassification {
  assistantType: AssistantType;
  confidence: number;
  reasoning: string;
  shouldSwitch: boolean;
}

export async function classifyIntent(
  userMessage: string,
  conversationHistory?: Array<{ role: string; content: string }>,
  currentAssistantType?: AssistantType
): Promise<IntentClassification> {
  const trimmed = userMessage.trim();
  const looksLikeGreetingOnly = /^(hi|hello|hey|yo|good\s+morning|good\s+afternoon|good\s+evening)(\s+there)?[!.\s]*$/i.test(
    trimmed
  );
  if (looksLikeGreetingOnly && (!conversationHistory || conversationHistory.length === 0)) {
    const fallbackType = currentAssistantType || getDefaultAssistantType();
    return {
      assistantType: fallbackType,
      confidence: 10,
      reasoning: 'Greeting-only message; keeping default assistant.',
      shouldSwitch: false,
    };
  }

  try {
    const messages: Array<{ role: 'system' | 'user'; content: string }> = [
      {
        role: 'system',
        content: `You are an intent classification system for a marketing chatbot. Your job is to determine which assistant type best matches the user's intent.

Available assistant types:
${Object.entries(ASSISTANT_TEMPLATES).map(([type, config]) => 
  `- ${type}: ${config.description}\n  Keywords: ${config.intentKeywords.join(', ')}`
).join('\n')}

CRITICAL RULE:
- "Opening a page", "Going to a page", "Navigating to", or "Editing a page" requests are ALWAYS classified as 'content_authoring'.
- NEVER classify page navigation requests as 'asset_manager'.

Analyze the user's message${conversationHistory ? ' and recent conversation context' : ''} to determine:
1. Which assistant type best matches their intent
2. Your confidence level (0-100)
3. Brief reasoning for your classification

${currentAssistantType ? `Current assistant type is: ${currentAssistantType}. Only recommend switching if the new intent is clearly different and confidence is high (>80).` : 'This is the first message, so classify the initial intent.'}

Respond with a JSON object in this format:
{
  "assistantType": "content_auditor|campaign_designer|seo_optimizer|asset_manager|content_authoring",
  "confidence": 85,
  "reasoning": "Brief explanation of why this type was chosen"
}`
      }
    ];

    // Add conversation history for context if reclassifying
    if (conversationHistory && conversationHistory.length > 0) {
      const recentHistory = conversationHistory.slice(-4); // Last 4 messages for context
      messages.push({
        role: 'user',
        content: `Recent conversation:\n${recentHistory.map(msg => `${msg.role}: ${msg.content}`).join('\n')}\n\nNew message: ${userMessage}`
      });
    } else {
      messages.push({
        role: 'user',
        content: userMessage
      });
    }

    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini', // Using mini for faster/cheaper classification
      messages,
      response_format: { type: 'json_object' },
      temperature: 0.3, // Lower temperature for more consistent classification
    });

    const result = JSON.parse(completion.choices[0].message.content || '{}');
    
    const assistantType = result.assistantType as AssistantType;
    const confidence = result.confidence || 0;
    
    // Determine if we should switch assistants
    const shouldSwitch = currentAssistantType 
      ? (assistantType !== currentAssistantType && confidence > 80)
      : true; // Always "switch" (set) on first message

    return {
      assistantType,
      confidence,
      reasoning: result.reasoning || 'No reasoning provided',
      shouldSwitch
    };
  } catch (error) {
    console.error('Error classifying intent:', error);
    
    // Fallback to keyword matching
    return fallbackIntentClassification(userMessage, currentAssistantType);
  }
}

// Fallback classification using simple keyword matching
function fallbackIntentClassification(
  userMessage: string,
  currentAssistantType?: AssistantType
): IntentClassification {
  const messageLower = userMessage.toLowerCase();
  const scores: Record<AssistantType, number> = {
    content_auditor: 0,
    campaign_designer: 0,
    seo_optimizer: 0,
    asset_manager: 0,
    content_authoring: 0
  };

  // Score each assistant type based on keyword matches
  Object.entries(ASSISTANT_TEMPLATES).forEach(([type, config]) => {
    config.intentKeywords.forEach(keyword => {
      if (messageLower.includes(keyword.toLowerCase())) {
        scores[type as AssistantType] += 1;
      }
    });
  });

  // Find the highest scoring type
  let maxScore = 0;
  let bestType: AssistantType = currentAssistantType || getDefaultAssistantType();
  
  Object.entries(scores).forEach(([type, score]) => {
    if (score > maxScore) {
      maxScore = score;
      bestType = type as AssistantType;
    }
  });

  const confidence = Math.min(maxScore * 25, 95); // Cap at 95% for fallback
  const shouldSwitch = currentAssistantType
    ? (bestType !== currentAssistantType && confidence > 60)
    : true;

  return {
    assistantType: bestType,
    confidence,
    reasoning: `Keyword-based classification (fallback). Matched ${maxScore} keywords for ${bestType}.`,
    shouldSwitch
  };
}
