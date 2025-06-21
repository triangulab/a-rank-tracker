FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN apt-get update && apt-get install -y dnsutils
RUN pip install --no-cache-dir -r requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
