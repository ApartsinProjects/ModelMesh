FROM python:3.12-slim
WORKDIR /app

# Copy only the Python package (pyproject.toml is inside src/python/)
COPY src/python/ ./src/python/

# Install the package + YAML support
RUN pip install --no-cache-dir "./src/python[yaml]"

# Copy optional YAML config if present
COPY modelmesh.example.yaml ./modelmesh.example.yaml

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/v1/models')" || exit 1

ENTRYPOINT ["python", "-m", "modelmesh.proxy"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
