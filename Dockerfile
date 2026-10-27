FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GUARDIAN_PORT=8098 \
    GUARDIAN_BIND_HOST=0.0.0.0 \
    GUARDIAN_INFERENCE_MODE=demo
WORKDIR /app
COPY guardian/ ./guardian/
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin guardian
USER 10001:10001
EXPOSE 8098
CMD ["python", "-m", "guardian.server"]
