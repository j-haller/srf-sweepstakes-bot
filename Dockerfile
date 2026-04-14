FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY srf-sweepstakes-bot.py .

CMD ["python", "srf-sweepstakes-bot.py"]
