FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml README.md LICENSE constraints-ci.txt ./
COPY src ./src
RUN python -m pip install --upgrade pip && python -m pip install --no-cache-dir .

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 mvia && useradd --uid 10001 --gid mvia --create-home mvia
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin/mvia /usr/local/bin/mvia
COPY --from=build /usr/local/bin/mvia-api /usr/local/bin/mvia-api
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
COPY tests/fixtures ./tests/fixtures
USER mvia
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]
CMD ["python", "-m", "uvicorn", "mvia.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
