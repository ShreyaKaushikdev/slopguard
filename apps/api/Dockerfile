FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY apps/api/slopguard ./slopguard

# Copy datasets (used for evaluation endpoints)
COPY datasets ./datasets

EXPOSE 8000

CMD ["uvicorn", "slopguard.main:app", "--host", "0.0.0.0", "--port", "8000"]
