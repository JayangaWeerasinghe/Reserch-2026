FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# CPU-only wheels: the default PyPI torch/torchvision pull ~1.3GB of unused CUDA/nvidia-* packages
RUN pip install --no-cache-dir torch==2.13.0+cpu torchvision==0.28.0+cpu --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY training ./training
COPY models ./models
COPY data ./data
EXPOSE 8002
CMD ["sh", "-c", "gunicorn -w 1 -b 0.0.0.0:${PORT:-8002} app.main:app --timeout 300"]
