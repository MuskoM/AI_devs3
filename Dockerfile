# Initial stage for installing wheel packages
FROM python:3.12.7-alpine3.20 AS builder

# Set working directory
WORKDIR /app
# Copy source files
COPY requirements.txt .

RUN apk add --no-cache gcc musl-dev linux-headers libffi-dev \
	&& pip install --upgrade pip \
	&& pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt

FROM python:3.12.7-alpine3.20

RUN addgroup -S app && adduser -S app -G app

USER app

# Prevents Python from writing .pyc files to disk, reducing clutter.
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures that the output is not buffered, which is useful for logging
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /wheels /wheels

COPY . .

RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

EXPOSE 8888

ENTRYPOINT "./run-server.sh"
