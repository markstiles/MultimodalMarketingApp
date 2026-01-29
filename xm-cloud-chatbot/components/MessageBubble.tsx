'use client';

import Image from 'next/image';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  images?: string[];
  assets?: Array<{
    kind: 'image' | 'file';
    url: string;
    thumbUrl?: string;
    name?: string;
    extension?: string;
    description?: string;
    width?: number;
    height?: number;
    altText?: string;
  }>;
  timestamp?: Date;
}

interface MessageBubbleProps {
  message: Message;
}

// Filter out metadata that shouldn't be displayed to users
function filterDisplayContent(content: string): string {
  return content
    .replace(/^Generated images?:\s*$/gim, '')           // "Generated images:"
    .replace(/^Image \d+\s*$/gim, '')                   // "Image 1", "Image 2"
    .replace(/^-?\s*\[Image \d+\]\([^)]*\)\s*$/gim, '') // "- [Image 1](url)"
    .replace(/^\s*\n\s*\n/gm, '\n')                     // Clean up extra blank lines
    .trim();
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const displayContent = filterDisplayContent(message.content);

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`${isUser ? 'max-w-[80%]' : 'w-full'} min-w-0 rounded-lg p-3 ${
          isUser
            ? 'bg-[#dddddd] text-black border border-gray-300'
            : 'bg-white text-gray-900 border border-gray-200'
        }`}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          className="prose prose-sm max-w-none text-current prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-1"
          components={{
            pre: ({ children }) => (
              <details className="my-2 border border-gray-200 rounded-md bg-gray-50 overflow-hidden group max-w-full">
                <summary className="px-3 py-2 bg-gray-100 text-xs font-semibold text-gray-600 cursor-pointer hover:bg-gray-200 transition-colors list-none flex items-center justify-between select-none">
                  <span>Code Snippet</span>
                  <svg className="w-4 h-4 transform group-open:rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </summary>
                <div className="grid">
                  <div className="p-3 overflow-x-auto bg-white w-full min-w-0">
                    <pre className="!m-0 !p-0 !bg-transparent text-sm font-mono whitespace-pre">
                      {children}
                    </pre>
                  </div>
                </div>
              </details>
            ),
            code: ({ node, inline, className, children, ...props }: {
              node?: unknown;
              inline?: boolean;
              className?: string;
              children?: React.ReactNode;
            }) => {
                if (inline) {
                   return (
                    <code
                      className={`${className || ''} px-1.5 py-0.5 bg-gray-100 text-red-500 rounded font-mono text-sm border border-gray-200`}
                      {...props}
                    >
                      {children}
                    </code>
                   );
                }
                return (
                  <code
                    className={`${className || ''} block text-gray-800 font-mono text-sm`}
                    {...props}
                  >
                    {children}
                  </code>
                );
            },
            img: () => null,
          }}
        >
          {displayContent}
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

        {message.assets && message.assets.length > 0 && (
          <>
            {/* Image Assets Grid */}
            {message.assets.filter(a => a.kind === 'image').length > 0 && (
              <div className="mt-2 grid grid-cols-4 gap-2">
                {message.assets.filter(a => a.kind === 'image').map((asset, idx) => {
                   const thumbUrl = asset.thumbUrl || `${asset.url}${asset.url.includes('?') ? '&' : '?'}w=300`;
                   const title = asset.name || asset.altText || 'Image asset';
                   const dimensions = asset.width && asset.height ? `${asset.width}x${asset.height}` : null;

                   return (
                     <a
                       key={idx}
                       href={asset.url}
                       target="_blank"
                       rel="noopener noreferrer"
                       className="block relative w-full overflow-hidden rounded-md border border-gray-200 bg-gray-50 aspect-square group"
                       title={title}
                     >
                       <Image
                         src={thumbUrl}
                         alt={asset.altText || title}
                         fill
                         className="object-cover"
                         sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
                         unoptimized
                       />
                       
                       {/* Transparent Hover Bar */}
                       <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] p-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200 truncate text-center">
                         {dimensions ? dimensions : (asset.extension ? `.${asset.extension}` : 'Image')}
                       </div>
                     </a>
                   );
                })}
              </div>
            )}

            {/* File Assets List */}
            {message.assets.filter(a => a.kind !== 'image').length > 0 && (
              <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {message.assets.filter(a => a.kind !== 'image').map((asset, idx) => (
                  <a
                    key={idx}
                    href={asset.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-3 rounded-md border border-gray-200 bg-gray-50 p-2 hover:bg-gray-100 transition-colors"
                    title={asset.url}
                  >
                    <span className="flex h-[56px] w-[56px] shrink-0 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-600">
                        <svg
                          className="h-6 w-6"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <path d="M14 2v6h6" />
                        </svg>
                    </span>

                    <span className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-gray-900">
                        {asset.name || asset.url}
                      </div>
                      <div className="truncate text-xs text-gray-500">
                        File
                        {asset.extension ? ` • .${asset.extension.replace(/^\./, '')}` : ''}
                      </div>
                    </span>
                  </a>
                ))}
              </div>
            )}
          </>
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
