# Use an official Python runtime as a parent image
FROM docker.io/python:3-slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

RUN opentelemetry-bootstrap --action=install

RUN pip uninstall opentelemetry-instrumentation-aws-lambda -y

# Make port 5001 available to the world outside this container
EXPOSE 5001

# Define environment variable
# ENV OTEL_LOGS_EXPORTER="otlp"
# ENV OTEL_METRICS_EXPORTER="otlp"
# ENV OTEL_TRACES_EXPORTER="console,otlp"
# ENV OTEL_EXPORTER_OTLP_ENDPOINT="localhost:4317"
# ENV OTEL_SERVICE_NAME=combined-flask
ENV OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=aws_lambda

# Run app.py when the container launches
CMD ["opentelemetry-instrument","python","app.py"]