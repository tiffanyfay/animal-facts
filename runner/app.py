from flask import Flask, request, jsonify
import requests
import os
import logging
from openai import OpenAI
from opentelemetry import trace
import time

# Acquire a tracer
tracer = trace.get_tracer("combined.tracer")

app = Flask(__name__)

@app.route('/', methods=['POST'])
def run():
    # Create a new span
    with tracer.start_as_current_span("runner") as generate_span:
        data = request.get_json()
        animal = data.get("animal")
        if not animal:
            error_message = "You must provide an animal"
            try:
                raise ValueError(error_message)
            except Exception as e:
                generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
                generate_span.record_exception(e)
            return jsonify({"error": error_message}), 400
        
        generate_span.set_attribute("runner.animal", animal)

        # Check if the animal is a string
        if not isinstance(animal, str):
            return jsonify({"error": "The animal must be a string"}), 400
        
        animal = str(animal).strip().lower()

        # Check if the animal contains any digits
        if any(char.isdigit() for char in animal):
            error_message = "The animal name must not contain numbers."
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            generate_span.record_exception(Exception(error_message))
            return jsonify({"error": error_message}), 400

        if animal == "snorblefox":
            error_message = f"The animal '{animal}' does not exist."
            try:
                raise ValueError(error_message)
            except Exception as e:
                generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
                generate_span.record_exception(e)
            logging.warning(error_message)
            return jsonify({"error": error_message}), 400
        
        # Sleep for 5 seconds if the animal is a goat
        if animal == "goat":
            with tracer.start_span("sleep_timer") as sleep_span:
                sleep_duration = 5
                sleep_span.set_attribute("sleep.duration_seconds", sleep_duration)
                time.sleep(sleep_duration)

        # Get a fact about the animal
        fact_response = requests.post("http://fact-generator:5001/generate", json={"animal": animal})
        fact = fact_response.json().get("result")
        generate_span.set_attribute("fact_generator.fact", fact)
        logging.info(f"Generated fact for {animal}: {fact}")

        # Get an image of the animal
        image_response = requests.post("http://image-generator:5002/generate", json={"prompt": fact})
        image_url = image_response.json().get("result")
        generate_span.set_attribute("image_generator.image_url", image_url)
        logging.info(f"Generated image for {animal}: {image_url}")
        return jsonify({"animal": animal, "fact": fact, "image_url": image_url})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)