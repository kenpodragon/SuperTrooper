FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for Claude CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI (optional — used for AI-enhanced resume parsing)
RUN npm install -g @anthropic-ai/claude-code || echo "Claude CLI install skipped"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Flask API + MCP SSE server (combined)
EXPOSE 8055 8056

CMD ["python", "app.py", "--mcp-port", "8056"]
