'use client';

import { useEffect, useState } from 'react';
import { EditorContext, MediaAssetContext, isValidEditorOrigin } from '@/lib/types/editor-messages';
import ChatPanel from '@/components/ChatPanel';

export default function EditorPanelPage() {
  // For local testing, initialize with mock context
  const [editorContext, setEditorContext] = useState<EditorContext | null>(
    process.env.NODE_ENV === 'development'
      ? {
          pageId: 'local-test-page-001',
          siteId: 'local-test-site-001',
          userId: 'mark.stiles@velir.com',
          siteName: 'multimodalmarketing',
          pagePath: '/test-page',
          language: 'en',
          environmentHost:
            process.env.NEXT_PUBLIC_ENVIRONMENT_HOST ||
            process.env.NEXT_PUBLIC_SITECORE_ENVIRONMENT_NAME,
        }
      : null
  );
  const [isReady, setIsReady] = useState(process.env.NODE_ENV === 'development');

  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      console.log('🧪 Running in development mode with mock editor context');
      return;
    }

    // Listen for messages from XM Cloud Pages Editor (production only)
    const handleMessage = (event: MessageEvent) => {
      // Validate origin
      if (!isValidEditorOrigin(event.origin)) {
        console.warn('Received message from invalid origin:', event.origin);
        return;
      }

      const message = event.data;

      switch (message.type) {
        case 'context':
          // Editor is providing initial context
          setEditorContext(() => {
            const raw = message.data as any;
            const pickEnv = (...values: Array<unknown>): string | undefined => {
              for (const v of values) {
                if (typeof v === 'string' && v.trim()) return v.trim();
              }
              return undefined;
            };

            const environmentHost = pickEnv(
              raw?.environmentHost,
              raw?.environment_host,
              raw?.ENVIRONMENT_HOST,
            );

            const normalized: EditorContext = {
              ...(raw as EditorContext),
              ...(environmentHost ? { environmentHost } : {}),
            };

            return normalized;
          });
          setIsReady(true);
          break;

        case 'page_changed':
          // User navigated to a different page
          setEditorContext((prev) => ({
            ...prev!,
            pageId: message.data.pageId,
            pagePath: message.data.pagePath,
          }));
          break;

        case 'component_selected':
          // User selected a component
          setEditorContext((prev) => ({
            ...prev!,
            selectedComponentId: message.data.componentId,
          }));
          break;

        case 'asset_selected':
          // User selected an asset in the media library
          setEditorContext((prev) => {
            const raw = message.data as any;
            const asset: MediaAssetContext = {
              itemId: raw?.itemId ?? raw?.id ?? raw?.item_id,
              path: raw?.path,
              type: raw?.type,
              altText: raw?.altText ?? raw?.alt_text,
              width: raw?.width,
              height: raw?.height,
              extension: raw?.extension,
              size: raw?.size,
              description: raw?.description,
              url: raw?.url,
            };

            return {
              ...prev!,
              selectedAsset: asset,
            };
          });
          break;

        default:
          console.log('Unknown message type:', message.type);
      }
    };

    window.addEventListener('message', handleMessage);

    // Send ready signal to parent
    if (window.parent !== window) {
      window.parent.postMessage({ type: 'ready' }, '*');
    }

    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);

  // Function to send messages back to the editor
  const sendToEditor = (message: unknown) => {
    if (window.parent !== window) {
      window.parent.postMessage(message, '*');
    }
  };

  if (!isReady || !editorContext) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Connecting to Pages Editor...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-white">
      <ChatPanel
        editorContext={editorContext}
        onSendToEditor={sendToEditor}
      />
    </div>
  );
}
