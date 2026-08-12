FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# chromium ships in the base image; make sure it matches this playwright version
RUN playwright install chromium
COPY app.py scraper.py ./
COPY static/ ./static/
RUN mkdir -p /data
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
