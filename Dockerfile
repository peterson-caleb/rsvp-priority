# Dockerfile
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY . .

# Expose the port Render expects
EXPOSE 10000

# The command to start the Gunicorn server
CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:10000"]