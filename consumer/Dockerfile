FROM python:3.8
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
COPY ./consumer.py /app/consumer.py
WORKDIR /app

CMD ["python", "consumer.py"]

