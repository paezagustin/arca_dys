FROM python:3.11-slim

ENV TZ=America/Argentina/Buenos_Aires

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY bill.html .

CMD ["python", "app.py"]
