# Generate self-signed SSL certificates for PostgreSQL
# Run this script once before starting the Docker container

Write-Host "Generating self-signed SSL certificates for PostgreSQL..." -ForegroundColor Cyan

$certsDir = Join-Path $PSScriptRoot "certs"

# Create certs directory if it doesn't exist
if (-not (Test-Path $certsDir)) {
    New-Item -ItemType Directory -Path $certsDir | Out-Null
}

# Navigate to certs directory
Push-Location $certsDir

# Generate private key
Write-Host "Generating private key..." -ForegroundColor Yellow
openssl genrsa -out server.key 2048

# Set permissions on private key (required by PostgreSQL)
if ($IsWindows -or $env:OS -match "Windows") {
    # On Windows, just ensure the file exists
    Write-Host "Note: On Windows, PostgreSQL in Docker will handle key permissions" -ForegroundColor Yellow
} else {
    chmod 600 server.key
}

# Generate certificate signing request
Write-Host "Generating certificate signing request..." -ForegroundColor Yellow
openssl req -new -key server.key -out server.csr -subj "/C=US/ST=State/L=City/O=Development/CN=localhost"

# Generate self-signed certificate (valid for 365 days)
Write-Host "Generating self-signed certificate..." -ForegroundColor Yellow
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt

# Clean up CSR
Remove-Item server.csr

Pop-Location

Write-Host "SSL certificates generated successfully!" -ForegroundColor Green
Write-Host "  - Private key: $certsDir\server.key" -ForegroundColor Gray
Write-Host "  - Certificate: $certsDir\server.crt" -ForegroundColor Gray
Write-Host ""
Write-Host "You can now start the PostgreSQL container with: docker-compose up -d" -ForegroundColor Cyan
