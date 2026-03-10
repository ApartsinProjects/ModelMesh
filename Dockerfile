FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src/python/ ./src/python/
RUN pip install . && pip install pyyaml>=6.0
EXPOSE 8080
ENTRYPOINT ["python", "-m", "modelmesh.proxy"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
