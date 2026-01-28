import { prisma } from '@/lib/db';
import { getClientCredentialsJwt } from '@/lib/sitecore/agent-api';
import { NextRequest } from 'next/server';

export async function getSmartToken(
  userId: string, 
  req: NextRequest, 
  emit: (payload: any) => void, 
  applicationContext: any
): Promise<string> {
    const userToken = (applicationContext as any)?.auth?.accessToken || 
                      (await prisma.oAuthToken.findUnique({ where: { userId } }))?.accessToken;

    // Try Service Token for Agent API, fallback to User Token
    const serviceToken = await getClientCredentialsJwt();
    const tokenToUse = serviceToken || userToken;
    
    if (!tokenToUse) {
            const referer = req.headers.get('referer') || '';
            const authUrl = `/api/auth/login?userId=${encodeURIComponent(userId)}&redirectUri=${encodeURIComponent(referer)}`;
            emit({ type: 'client_action', action: 'auth_required', data: { url: authUrl } });
            await new Promise(r => setTimeout(r, 100));
            throw new Error('Authentication required.');
    }
    return tokenToUse;
}
