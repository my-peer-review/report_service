# --- Base image Python ---
FROM python:3.11-slim

# --- Workdir ---
WORKDIR /work
RUN mkdir -p /var/run/secrets/kubernetes.io/serviceaccount

# --- Install dependencies ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy source code ---
COPY app ./app

# --- Expose port & run with uvicorn ---
EXPOSE 9090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9090"]