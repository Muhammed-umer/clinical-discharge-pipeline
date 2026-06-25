# Use the official slim Python runtime image
FROM python:3.12-slim

# Set environment system guardrails
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Establish the working directory inside the container
WORKDIR /code

# Install system dependencies needed to compile PostgreSQL drivers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements configuration and install dependencies
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the entire app layout folder into the container workspace
COPY ./app /code/app

# Expose port 8000 for network routing
EXPOSE 8000

# Command to run the production ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]