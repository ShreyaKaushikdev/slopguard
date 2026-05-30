FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY slopguard ./slopguard

EXPOSE 8000

CMD ["uvicorn", "slopguard.main:app", "--host", "0.0.0.0", "--port", "8000"]
