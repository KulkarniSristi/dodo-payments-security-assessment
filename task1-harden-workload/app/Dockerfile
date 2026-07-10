FROM python:3.11-slim-bookworm AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/install -r requirements.txt

FROM gcr.io/distroless/python3-debian12
WORKDIR /app
COPY --from=builder /install /install
ENV PYTHONPATH=/install
COPY app.py .
EXPOSE 8080
CMD ["app.py"]
