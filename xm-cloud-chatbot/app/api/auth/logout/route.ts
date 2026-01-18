import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { userId } = body;

    if (!userId) {
      return NextResponse.json(
        { error: 'userId is required' },
        { status: 400 }
      );
    }

    // Delete the OAuth token for this user
    await prisma.oAuthToken.delete({
      where: { userId },
    }).catch(() => {
      // Ignore if token doesn't exist
    });

    return NextResponse.json({
      success: true,
      message: 'Token deleted. Please re-authenticate.',
    });
  } catch (error) {
    console.error('Error deleting token:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
