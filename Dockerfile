FROM selenium/standalone-chrome:latest

USER root

WORKDIR /app

COPY requirements.txt .

# Update and install requirements, then clean up.
RUN apt-get update && \
  apt-get install -y python3 python3-pip gosu && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  pip3 install --upgrade pip && \
  pip3 install --no-cache-dir -r requirements.txt

COPY *.py .
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
