#!/usr/bin/env python3
"""Pre-flight validation: env vars (Pass 1) and port availability (Pass 2)."""

import os
import socket
import sys

from dotenv import load_dotenv

load_dotenv()

REQUIRED_SECRETS = ["LLM_API_KEY"]

REQUIRED_PORTS = [
    (3000, "Next.js frontend"),
    (5000, "MLflow"),
    (5432, "PostgreSQL"),
    (8000, "FastAPI backend"),
]


def check_env_vars() -> None:
    for var in REQUIRED_SECRETS:
        if not os.environ.get(var):
            print(f"ERROR: {var} is required but not set", file=sys.stderr)
            sys.exit(1)
    print("✓ Environment OK")


def check_ports() -> None:
    for port, service in REQUIRED_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                print(f"ERROR: port {port} is in use (required by: {service})", file=sys.stderr)
                sys.exit(1)
    print("✓ Ports OK")


if __name__ == "__main__":
    check_env_vars()
    check_ports()
