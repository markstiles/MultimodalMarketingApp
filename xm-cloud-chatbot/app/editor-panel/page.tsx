'use client';

import { useEffect, useState } from 'react';
import { MediaAssetContext, isValidEditorOrigin } from '@/lib/types/editor-messages';
import ChatPanel from '@/components/ChatPanel';
import { useMarketplaceClient } from '@/lib/hooks/use-marketplace-client';
import { ApplicationContext, PagesContext, UserInfo } from '@sitecore-marketplace-sdk/client';

export default function EditorPanelPage() {
  const { client, error, isInitialized } = useMarketplaceClient();
  const [appContext, setAppContext] = useState<ApplicationContext>();
  const [pagesContext, setPagesContext] = useState<PagesContext>();
  const [userInfo, setUserInfo] = useState<UserInfo>();
  const [selectedAsset, setSelectedAsset] = useState<MediaAssetContext | undefined>();
  const [selectedComponentId, setSelectedComponentId] = useState<string | undefined>();
  
  // Consider the panel ready once the Marketplace contexts are present.
  const isReady = !!(appContext?.id && pagesContext?.siteInfo?.id && pagesContext?.pageInfo?.id && userInfo?.id);
  const [isStandalone, setIsStandalone] = useState(false);

  useEffect(() => {
    setIsStandalone(window.parent === window);

    if (!error && isInitialized && client) {
      console.log("Marketplace client initialized successfully.");
      // Make a query to retrieve the application context
      client.query("application.context")
        .then((res) => {
          console.log("Success retrieving application.context:", res.data);
          setAppContext(res.data);
        })
        .catch((error) => {
          console.error("Error retrieving application.context:", error);
        });

      // Retrieve host user info (for conversation persistence + OAuth identity)
      client.query('host.user')
        .then((res) => {
          console.log('Success retrieving host.user - Raw Response:', JSON.stringify(res, null, 2));
          
          const rawData = res.data as any;
          // Map OIDC profile fields to our UserInfo structure
          // sub is the standard Subject identifier in OIDC
          const userId = rawData?.sub || rawData?.id || rawData?.sc_sys_id;
          
          if (userId) {
             console.log('Valid User Context ID found:', userId);
             setUserInfo({
                id: userId,
                name: rawData.name || rawData.nickname || 'Unknown User',
                email: rawData.email || ''
             });
          } else {
             console.warn('Host user returned empty data structure:', res.data);
             // Fallback for cases where host.user is blocked or unavailable
             setUserInfo({ 
               id: 'anonymous-user-' + Date.now(), 
               name: 'Anonymous User', 
               email: 'anonymous@example.com'
             });
          }
        })
        .catch((error) => {
          console.error('Error retrieving host.user:', error);
          // Fallback on error to prevent app hanging
          setUserInfo({ 
             id: 'fallback-user-' + Date.now(), 
             name: 'Fallback User', 
             email: 'fallback@example.com'
          });
        });

      client.query("pages.context", { 
        subscribe: true,
        onSuccess: (data) => {
          console.log('Page has been updated:', data);
          setPagesContext(data);
        },
      })
        .then((res) => {
          console.log("Success retrieving pages.context:", res.data);
          setPagesContext(res.data);
        })
        .catch((error) => {
          console.error("Error retrieving pages.context:", error);
        });
    } else if (error) {
      console.error("Error initializing Marketplace client:", error);
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
        case 'component_selected':
          // User selected a component
          setSelectedComponentId(message.data.componentId);
          break;

        case 'asset_selected':
          // User selected an asset in the media library
          {
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

            setSelectedAsset(asset);
          }
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
  }, [client, error, isInitialized]);

  // Function to send messages back to the editor
  const sendToEditor = (message: unknown) => {
    if (window.parent !== window) {
      window.parent.postMessage(message, '*');
    }
  };

  const environmentHost =
    process.env.NEXT_PUBLIC_ENVIRONMENT_HOST ||
    process.env.NEXT_PUBLIC_SITECORE_ENVIRONMENT_NAME;

  if (!isReady || !appContext || !pagesContext || !userInfo) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          {error ? (
             <div className="text-red-500 mb-4">
               <p className="font-bold">Connection Error</p>
               <p className="text-sm">{error.message}</p>
             </div>
          ) : isStandalone ? (
            <div className="text-amber-600 mb-4 max-w-md">
              <p className="font-bold text-lg mb-2">Standalone Mode Detected</p>
              <p className="text-sm text-gray-700">
                This application is running outside of the Sitecore Pages Editor and the mock context has been disabled.
                To use the chatbot, please open this page within Sitecore Pages or enable mock context for local development.
              </p>
            </div>
          ) : (
            <>
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Connecting to Pages Editor...</p>
            </>
          )}
          
          <div className="mt-8 text-left text-xs text-gray-400 bg-gray-100 p-4 rounded border border-gray-200">
            <p className="font-semibold mb-2">Connection Diagnostics:</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <span>SDK Initialized:</span>
              <span className={isInitialized ? "text-green-600" : "text-amber-600"}>{isInitialized ? "Yes" : "Pending..."}</span>
              
              <span>App Context:</span>
              <span className={appContext?.id ? "text-green-600" : "text-amber-600"}>{appContext?.id ? "Ready" : "Waiting"}</span>
              
              <span>Site Context:</span>
              <span className={pagesContext?.siteInfo?.id ? "text-green-600" : "text-amber-600"}>{pagesContext?.siteInfo?.id ? "Ready" : "Waiting"}</span>
              
              <span>Page Context:</span>
              <span className={pagesContext?.pageInfo?.id ? "text-green-600" : "text-amber-600"}>{pagesContext?.pageInfo?.id ? "Ready" : "Waiting"}</span>
              
              <span>User Context:</span>
              <span className={userInfo?.id ? "text-green-600" : "text-amber-600"}>{userInfo?.id ? "Ready" : "Waiting"}</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-white">
      <ChatPanel
        applicationContext={appContext}
        pagesContext={pagesContext}
        user={userInfo}
        environmentHost={environmentHost}
        selectedAsset={selectedAsset}
        selectedComponentId={selectedComponentId}
        onSendToEditor={sendToEditor}
      />
    </div>
  );
}
