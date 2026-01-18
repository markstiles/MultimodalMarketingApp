-- Create oAuthToken table
CREATE TABLE IF NOT EXISTS "oAuthToken" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "accessToken" TEXT NOT NULL,
    "refreshToken" TEXT,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "scope" TEXT,
    "tokenType" TEXT NOT NULL DEFAULT 'Bearer',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT "oAuthToken_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "oAuthToken_userId_key" UNIQUE ("userId")
);

-- Create indexes
CREATE INDEX IF NOT EXISTS "oAuthToken_userId_idx" ON "oAuthToken"("userId");
CREATE INDEX IF NOT EXISTS "oAuthToken_expiresAt_idx" ON "oAuthToken"("expiresAt");
