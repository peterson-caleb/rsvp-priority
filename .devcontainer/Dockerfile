FROM mcr.microsoft.com/devcontainers/python:3.12

# Copy requirements and install packages
WORKDIR /workspaces/rsvp-priority
COPY ../requirements.txt .
RUN pip install --user -r requirements.txt