FROM node:22-alpine AS ui-build
WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm install
COPY ui/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt* ./
RUN pip install --no-cache-dir pytest sqlalchemy

COPY . /app
COPY --from=ui-build /app/ui/dist /app/ui/dist

EXPOSE 5173
CMD ["python", "cli/main.py", "benchmark"]
