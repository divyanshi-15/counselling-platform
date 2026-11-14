FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed

WORKDIR /app

# Embedding model is baked into the image (outside /app so test bind-mounts don't hide it).
# This layer only rebuilds when the fastembed pin changes, so the model is downloaded once.
RUN pip install --upgrade pip setuptools wheel && \
    pip install "fastembed>=0.9,<0.10" && \
    python -c "from fastembed import TextEmbedding; from fastembed.common.model_description import ModelSource, PoolingType; m='intfloat/multilingual-e5-small'; TextEmbedding.add_custom_model(model=m, pooling=PoolingType.MEAN, normalization=True, sources=ModelSource(hf=m), dim=384, model_file='onnx/model.onnx'); list(TextEmbedding(m, cache_dir='/opt/fastembed').embed(['passage: warmup']))"

COPY pyproject.toml ./
COPY backend ./backend
COPY kb ./kb

RUN pip install .[dev]

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
