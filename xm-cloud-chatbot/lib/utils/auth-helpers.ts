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

export function redirectToLogin(userId: string, redirectUri?: string): void {
  const loginUrl = new URL('/api/auth/login', window.location.origin);
  loginUrl.searchParams.set('userId', userId);
  if (redirectUri) {
    loginUrl.searchParams.set('redirectUri', redirectUri);
  }
  window.location.href = loginUrl.toString();
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

