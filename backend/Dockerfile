FROM python:3.11-slim
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# Non-root: the app only needs to read its own code and bind a high port.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /code
USER appuser
EXPOSE 8000
# Shell form so hosts like Render/Railway can inject $PORT.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
