FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY jobfinder ./jobfinder
COPY resume.example.txt profile.example.yaml ./
RUN pip install --no-cache-dir -e .

EXPOSE 5000
CMD ["python", "-m", "jobfinder", "serve", "--host", "0.0.0.0", "--port", "5000"]
