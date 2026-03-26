# Use the official lightweight Python image.
FROM python:3.11-slim

# Install system dependencies required by ODA File Converter and ezdxf
RUN apt-get update && apt-get install -y \
    wget \
    fontconfig \
    libfreetype6 \
    libxrender1 \
    libxext6 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application files
COPY . .

# Try to install ODA File Converter if the user downloaded the .deb file
# (This ensures the DWG export feature works in production)
RUN if ls ODAFileConverter*.deb 1> /dev/null 2>&1; then \
        dpkg -i ODAFileConverter*.deb || apt-get install -f -y; \
    else \
        echo "\nWARNING: ODAFileConverter.deb not found in the repository!\nDWG generation will return an error.\n"; \
    fi

# Expose the standard Flask/Gunicorn port
EXPOSE 5000

# Run the application with Gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
