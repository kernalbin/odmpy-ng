FROM selenium/standalone-chrome:latest

USER root

RUN apt-get update && apt-get install -y python3 python3-pip

COPY requirements.txt /app/requirements.txt
 
RUN pip3 install --upgrade -r /app/requirements.txt

WORKDIR /app

COPY *.py /app

CMD ["python3", "interactive.py", "/config/config.json"]