# Tuesday — Personal AI Assistant
# Multi-stage build: frontend → backend serving everything

# --- Stage 1: Build frontend ---
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python backend + serve frontend ---
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/

# Copy knowledge files
COPY knowledge/ ./knowledge/

# Copy built frontend into frontend/dist (FastAPI serves this)
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Create runtime directories
RUN mkdir -p backend/sessions backend/logs backend/uploads backend/outputs backend/briefings

# Expose port
EXPOSE 8000

# Run with uvicorn
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
