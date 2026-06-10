// Helper hook to check authentication and trigger OAuth flow if needed

export interface AuthStatus {
  authenticated: boolean;
  requiresAuth: boolean;
  expiresAt?: string;
  error?: string;
}

export async function checkAuthStatus(userId: string): Promise<AuthStatus> {
  try {
    const response = await fetch(`/api/auth/status?userId=${encodeURIComponent(userId)}`);
    
    if (!response.ok) {
      return {
        authenticated: false,
        requiresAuth: true,
        error: 'Failed to check authentication status',
      };
    }

    return await response.json();
  } catch (error) {
    console.error('Error checking auth status:', error);
    return {
      authenticated: false,
      requiresAuth: true,
      error: 'Network error checking authentication',
    };
  }
}

export async function redirectToLogin(userId: string, redirectUri?: string): Promise<void> {
  // Pre-open the window to avoid async popup blocking
  const authWindow = window.open('about:blank', 'sitecore_auth_popup', 'width=800,height=600');
  if (authWindow) {
    authWindow.document.write('Can\'t assume model loaded... Please wait while we initialize authentication...');
  }
  
  const loginUrl = new URL('/api/auth/login', window.location.origin);
  loginUrl.searchParams.set('userId', userId);
  if (redirectUri) {
    loginUrl.searchParams.set('redirectUri', redirectUri);
  }
  
  // Use fetch instead of direct navigation to get the auth URL while preserving CORS headers
  try {
    console.log('[Auth] Initiating login request...', loginUrl.toString());
    
    // Explicitly add a trailing slash to origin if needed, or ensure it matches exact PNA expectations
    // PNA requires preflight. Fetch will trigger preflight if we add custom headers or if it's cross-origin
    const response = await fetch(loginUrl.toString(), {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        // 'Content-Type': 'application/json' // Removing this as it's a GET request
      }
    });

    console.log('[Auth] Login API status:', response.status);

    if (!response.ok) {
      console.error('[Auth] Login response not OK:', await response.text());
      return;
    }

    const data = await response.json();
    console.log('[Auth] Received login data URL:', data.url ? 'Yes' : 'No');

    if (data.url) {
      console.log('[Auth] Redirecting to:', data.url);
      
      if (authWindow) {
        authWindow.location.href = data.url;
      } else {
        // Fallback for when popup was blocked initially (rare but possible)
        window.open(data.url, '_blank', 'width=800,height=600');
      }
    } else {
      console.error('Failed to get login URL', data);
      if (authWindow) authWindow.close();
    }
  } catch (error) {
    console.error('Error initiating login:', error);
    if (authWindow) authWindow.close();
  }
}

export async function refreshToken(userId: string): Promise<boolean> {
  try {
    const response = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ userId }),
    });

    if (!response.ok) {
      return false;
    }

    const data = await response.json();
    return data.success === true;
  } catch (error) {
    console.error('Error refreshing token:', error);
    return false;
  }
}

