# Dockerfile for ReliaKit
# Use a slim Python image for smaller size
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED 1

# Install system dependencies for Tkinter and SQLite3
RUN apt-get update && apt-get install -y \
    tk \
    sqlite3 \
    jq \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Create application directories
# Ensure 'reliakit/utils' exists for the database
RUN mkdir -p /app/reliakit/utils /app/generated_configs

# Copy the entire project into the container
COPY . /app

# Set the working directory
WORKDIR /app

# Install Python dependencies
# Ensure requirements.txt exists in the root of your context
RUN pip install --no-cache-dir -U pip setuptools wheel
RUN pip install -r requirements.txt

# Expose the Flask port (5001 to avoid common conflicts)
EXPOSE 5001

# Command to run the application
# This will start the web dashboard and the GUI (if X11 is forwarded)
# You can adjust this to run your start_reliakit.sh script directly if preferred
# CMD ["python3", "gui_launcher.py"] # For GUI only
# CMD ["python3", "reliakit/reliakit_web_dashboard.py"] # For web dashboard only

# To run the full system with the start_reliakit.sh script:
# Ensure start_reliakit.sh is executable: chmod +x start_reliakit.sh on host
CMD ["./start_reliakit.sh"]