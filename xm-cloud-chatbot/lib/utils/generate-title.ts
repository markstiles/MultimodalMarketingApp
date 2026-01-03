import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function generateConversationTitle(
  messages: Array<{ role: string; content: string }>
): Promise<string> {
  try {
    // Use the first 3 messages to understand conversation topic
    const contextMessages = messages.slice(0, 3);
    
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content: 'Generate a concise, descriptive title (max 50 characters) for this conversation. The title should capture the main topic or goal. Respond with only the title, no quotes or additional text.'
        },
        {
          role: 'user',
          content: `Conversation:\n${contextMessages.map(msg => `${msg.role}: ${msg.content}`).join('\n')}\n\nGenerate a title:`
        }
      ],
      temperature: 0.7,
      max_tokens: 20,
    });

    let title = completion.choices[0].message.content?.trim() || 'Untitled Conversation';
    
    // Remove quotes if present
    title = title.replace(/^["']|["']$/g, '');
    
    // Truncate if too long
    if (title.length > 50) {
      title = title.substring(0, 47) + '...';
    }

    return title;
  } catch (error) {
    console.error('Error generating conversation title:', error);
    
    // Fallback: use first message as basis for title
    const firstUserMessage = messages.find(m => m.role === 'user')?.content || '';
    if (firstUserMessage.length > 50) {
      return firstUserMessage.substring(0, 47) + '...';
    }
    return firstUserMessage || 'Untitled Conversation';
  }
}
