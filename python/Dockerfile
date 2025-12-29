FROM python:3.11-slim

WORKDIR /app

# Install UV for dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml pyproject.toml

# Install dependencies using UV
RUN uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install --system -r requirements.txt

# Copy source code
COPY . .

# Create non-root user
RUN useradd -m -u 65532 agentic && chown -R agentic:agentic /app
USER agentic

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run the server (app is created by to_a2a() in agent/server/server.py)
CMD ["python", "-m", "uvicorn", "agent.server:app", "--host", "0.0.0.0", "--port", "8000"]
