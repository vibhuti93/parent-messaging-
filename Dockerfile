FROM python:3.11-slim-bookworm

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /workspace

# 1. Install OS packages: FFmpeg, Poppler, Noto fonts, and font utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    poppler-utils \
    fonts-noto-core \
    fontconfig \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Rebuild font cache so Devanagari glyphs are indexed
RUN fc-cache -f -v

# 3. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. Install Chromium browser binary and its shared system libraries
RUN playwright install --with-deps chromium

# Default command
CMD ["bash"]