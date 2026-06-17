FROM python:3.12-slim

WORKDIR /app

# Dépendances d'abord (cache Docker).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code du service.
COPY . .

# Tous les services Voxenfer écoutent sur 5000.
EXPOSE 5000

# Healthcheck léger (le compose / la gateway peuvent s'en servir).
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:5000/health').status==200 else sys.exit(1)"

CMD ["python", "app.py"]
