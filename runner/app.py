from flask import Flask, request, jsonify
import requests
import os
import logging
from openai import OpenAI
from opentelemetry import trace

# Acquire a tracer
tracer = trace.get_tracer("combined.tracer")

app = Flask(__name__)

# Set your OpenAI API key from an environment variable
# openai.api_key = os.environ.get("OPENAI_API_KEY")


@app.route('/generate', methods=['POST'])
def run():
    # Create a new span for the generate endpoint
    with tracer.start_as_current_span("runner") as generate_span:
        data = request.get_json()
        animal = data.get("animal")
        if not animal:
            return jsonify({"error": "You must provide an animal"}), 400

        # Get a fact about the animal
        fact_response = requests.post("http://localhost:5001/generate", json={"animal": animal})
        fact = fact_response.json().get("result")

        # Get an image of the animal
        image_response = requests.post("http://localhost:5002/generate", json={"prompt": fact})
        image_url = image_response.json().get("result")

        return jsonify({"animal": animal, "fact": fact, "image_url": image_url})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)