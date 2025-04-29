FROM selenium/standalone-chrome:latest

ARG HOST_UID=1000
ARG HOST_GID=1000

USER root

# Update and install requirements, then clean up.
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /downloads

WORKDIR /app

COPY requirements.txt .
 
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY *.py .
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]