'use client';

import Image from 'next/image';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  images?: string[];
  timestamp?: Date;
}

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`${isUser ? 'max-w-[80%]' : 'w-full'} rounded-lg p-3 ${
          isUser
            ? 'bg-[#dddddd] text-black border border-gray-300'
            : 'bg-white text-gray-900 border border-gray-200'
        }`}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          className="prose prose-sm max-w-none text-current prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-1"
          components={{
            code: ({ node, inline, className, children, ...props }: {
              node?: unknown;
              inline?: boolean;
              className?: string;
              children?: React.ReactNode;
            }) => (
              <code
                className={`${className || ''} ${inline ? '' : 'block p-2 bg-gray-100 rounded-md text-gray-800'}`}
                {...props}
              >
                {children}
              </code>
            ),
            img: () => null,
          }}
        >
          {message.content}
        </ReactMarkdown>
        {message.images && message.images.length > 0 && (
          <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2">
            {message.images.map((url, idx) => (
              <a
                key={idx}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="block relative w-full overflow-hidden rounded-md border border-gray-200 bg-gray-50"
              >
                <Image
                  src={url}
                  alt={`Generated image ${idx + 1}`}
                  width={512}
                  height={512}
                  className="h-auto w-full object-cover"
                  sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
                />
              </a>
            ))}
          </div>
        )}
        {message.timestamp && (
          <div
            className={`text-xs mt-1 ${
              isUser ? 'text-[#444444]' : 'text-gray-500'
            }`}
          >
            {message.timestamp.toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        )}
      </div>
    </div>
  );
}
