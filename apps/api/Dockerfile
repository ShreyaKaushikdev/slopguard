FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY slopguard ./slopguard

# Copy datasets (optional — falls back gracefully if missing)
COPY datasets ./datasets

EXPOSE 8000

CMD ["uvicorn", "slopguard.main:app", "--host", "0.0.0.0", "--port", "8000"]
