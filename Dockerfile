FROM python:3.11-slim

ENV TZ=Europe/Rome
RUN apt-get update && apt-get install -y --no-install-recommends tzdata fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
ENV PORT=8080

CMD ["python", "server.py"]
