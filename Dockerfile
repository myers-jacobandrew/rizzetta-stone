FROM python:3.12-slim

# Unbuffered so print()/logs show up immediately in `docker logs`.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py slang.py urban.py db.py ./

# Learned words live here; mount a volume at /data so they survive redeploys.
ENV SLANG_DB=/data/slang.db

# Run as non-root. Create /data owned by the app user *before* declaring the
# VOLUME so a fresh named volume inherits writable ownership.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data && chown appuser:appuser /data /app
VOLUME ["/data"]
USER appuser

CMD ["python", "bot.py"]
