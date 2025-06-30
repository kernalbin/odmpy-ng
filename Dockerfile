# Use selenium's standalone chrome image (includes Chrome+WebDriver)
FROM selenium/standalone-chrome:latest

# Switch to root to install dependencies
USER root

# Set working directory
WORKDIR /app

# Get python dependency file
COPY requirements.txt .

# Install system packages and python dependencies
RUN apt-get update && \
    apt-get install -y python3 python3-pip gosu && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy python scripts and entrypoint
COPY *.py ./
COPY entrypoint.sh /entrypoint.sh

# Make entrypoint executable
RUN chmod +x /entrypoint.sh

# Supress pkg_resources deprecation warning until upstream resolves
ENV PYTHONWARNINGS="ignore:pkg_resources is deprecated as an API"

# command to run the app (will accept arguments)
ENTRYPOINT ["/entrypoint.sh"]
# default arguments to pass to the entrypoint
CMD []

