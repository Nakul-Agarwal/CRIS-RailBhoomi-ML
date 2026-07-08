# ============================================================
# Rail Bhoomi ML — Docker Image
# AI-Based Project Milestone Prediction System
# Author: Nakul Agarwal, CRIS Internship 2026
# ============================================================
#
# BUILD:   docker build -t railbhoomi-ml .
# RUN:     docker run -d -p 5000:5000 --name railbhoomi railbhoomi-ml
# OPEN:    http://localhost:5000
# STOP:    docker stop railbhoomi
# RETRAIN: docker exec railbhoomi python3 train_model.py
#          docker restart railbhoomi
# ============================================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Create logs directory
RUN mkdir -p logs

# Retrain model during build so pkl files match
# exact scikit-learn version installed above
RUN python3 train_model.py

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Start with Gunicorn — production grade server
CMD ["gunicorn", "app:app", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "logs/access.log", \
     "--error-logfile", "logs/error.log"]
