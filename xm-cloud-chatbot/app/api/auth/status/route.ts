import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const userId = searchParams.get('userId');

  if (!userId) {
    return NextResponse.json(
      { error: 'userId is required' },
      { status: 400 }
    );
  }

  try {
    const tokenRecord = await prisma.oAuthToken.findUnique({
      where: { userId },
      select: {
        expiresAt: true,
        updatedAt: true,
      },
    });

    if (!tokenRecord) {
      return NextResponse.json({
        authenticated: false,
        requiresAuth: true,
      });
    }

    // Check if token is expired (with 5-minute buffer)
    const isExpired = tokenRecord.expiresAt.getTime() - Date.now() < 5 * 60 * 1000;

    return NextResponse.json({
      authenticated: !isExpired,
      requiresAuth: isExpired,
      expiresAt: tokenRecord.expiresAt.toISOString(),
    });
  } catch (error) {
    console.error('Error checking auth status:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
