from flask import Flask, request, jsonify
import requests
import os
import logging
import socket
from openai import OpenAI
from opentelemetry import trace
from typing import Tuple
import time

# Acquire a tracer
tracer = trace.get_tracer("combined.tracer")

app = Flask(__name__)

logger = logging.getLogger("runner")
logging.basicConfig(level=logging.INFO)


def check_tcp(host: str, port: int, timeout: float = 1.0) -> Tuple[bool, str]:
    try:
        logger.debug(f"Checking connectivity to {host}:{port}")
        with socket.create_connection((host, port), timeout=timeout):
            logger.info(f"Connection OK: {host}:{port}")
            return True, ""
    except Exception as e:
        logger.error(f"Connection FAILED: {host}:{port} -> {e}")
        return False, str(e)


@app.route('/health', methods=['GET'])
def health_check():
    logger.info("Health check invoked")

    fact_host, fact_port = "fact-generator", 5001
    image_host, image_port = "image-generator", 5002

    timeout_seconds = 1.0

    ok_fact, fact_err = check_tcp(fact_host, fact_port, timeout_seconds)
    ok_image, image_err = check_tcp(image_host, image_port, timeout_seconds)

    status_parts = []

    if ok_fact:
        status_parts.append("fact-generator:ok")
    else:
        status_parts.append(f"fact-generator:error:{fact_err}")

    if ok_image:
        status_parts.append("image-generator:ok")
    else:
        status_parts.append(f"image-generator:error:{image_err}")

    status_msg = ", ".join(status_parts)

    logger.info(f"Health check result: {status_msg}")

    if ok_fact and ok_image:
        logger.info("Overall health: OK")
        return status_msg, 200
    else:
        logger.warning("Overall health: DEGRADED")
        return status_msg, 503



TIMEOUT = 30  # seconds for downstream calls

@app.route('/', methods=['POST'])
def run():
    with tracer.start_as_current_span("runner") as generate_span:
        data = request.get_json(silent=True)
        logger.info("Incoming request json: %s", data)
        if not data:
            error_message = "Invalid or missing JSON body"
            logger.warning(error_message)
            return jsonify({"error": error_message}), 400

        animal = data.get("animal")
        if not animal:
            error_message = "You must provide an animal"
            logger.warning(error_message)
            return jsonify({"error": error_message}), 400

        generate_span.set_attribute("runner.animal", str(animal))
        if not isinstance(animal, str):
            return jsonify({"error": "The animal must be a string"}), 400

        animal = str(animal).strip().lower()
        if any(char.isdigit() for char in animal):
            error_message = "The animal name must not contain numbers."
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            generate_span.record_exception(Exception(error_message))
            logger.warning(error_message)
            return jsonify({"error": error_message}), 400

        if animal == "snorblefox":
            error_message = f"The animal '{animal}' does not exist."
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            generate_span.record_exception(ValueError(error_message))
            logger.warning(error_message)
            return jsonify({"error": error_message}), 400

        # optional sleep for goat (keep existing behaviour)
        if animal == "goat":
            with tracer.start_span("sleep_timer") as sleep_span:
                sleep_duration = 5
                sleep_span.set_attribute("sleep.duration_seconds", sleep_duration)
                time.sleep(sleep_duration)

        # ---- Fact generator call (robust) ----
        fact_url = os.environ.get("FACT_GENERATOR_URL", "http://fact-generator:5001/")
        try:
            logger.info("Calling fact-generator %s with %s", fact_url, animal)
            fact_response = requests.post(fact_url, json={"animal": animal}, timeout=TIMEOUT)
            logger.info("fact-generator status=%s body=%s", fact_response.status_code, fact_response.text[:1000])
        except requests.RequestException as e:
            logger.exception("Failed to call fact-generator")
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            generate_span.record_exception(e)
            return jsonify({"error": "Failed to contact fact-generator"}), 502

        if not fact_response.ok:
            logger.error("fact-generator returned non-OK status %s: %s", fact_response.status_code, fact_response.text)
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            return jsonify({"error": "fact-generator error"}), 502

        try:
            fact_json = fact_response.json()
        except ValueError:
            logger.error("fact-generator returned invalid JSON: %s", fact_response.text)
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            generate_span.record_exception(Exception("Invalid JSON from fact-generator"))
            return jsonify({"error": "Invalid response from fact-generator"}), 502

        fact = fact_json.get("result")
        generate_span.set_attribute("fact_generator.fact", fact)
        logger.info("Generated fact for %s: %s", animal, (fact or "")[:200])

        # ---- Image generator call (robust) ----
        image_url = os.environ.get("IMAGE_GENERATOR_URL", "http://image-generator:5002/")
        try:
            logger.info("Calling image-generator %s with prompt", image_url)
            image_response = requests.post(image_url, json={"prompt": fact}, timeout=TIMEOUT)
            logger.info("image-generator status=%s body=%s", image_response.status_code, image_response.text[:1000])
        except requests.RequestException as e:
            logger.exception("Failed to call image-generator")
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            generate_span.record_exception(e)
            return jsonify({"error": "Failed to contact image-generator"}), 502

        if not image_response.ok:
            logger.error("image-generator returned non-OK status %s: %s", image_response.status_code, image_response.text)
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            return jsonify({"error": "image-generator error"}), 502

        try:
            image_json = image_response.json()
        except ValueError:
            logger.error("image-generator returned invalid JSON: %s", image_response.text)
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            generate_span.record_exception(Exception("Invalid JSON from image-generator"))
            return jsonify({"error": "Invalid response from image-generator"}), 502

        image_url_res = image_json.get("result")
        generate_span.set_attribute("image_generator.image_url", image_url_res)
        logger.info("Generated image for %s: %s", animal, image_url_res)

        return jsonify({"animal": animal, "fact": fact, "image_url": image_url_res}), 200

# @app.route('/', methods=['POST'])
# def run():
#     # Create a new span
#     with tracer.start_as_current_span("runner") as generate_span:
#         data = request.get_json()
#         animal = data.get("animal")
#         if not animal:
#             error_message = "You must provide an animal"
#             try:
#                 raise ValueError(error_message)
#             except Exception as e:
#                 generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
#                 generate_span.record_exception(e)
#             return jsonify({"error": error_message}), 400
        
#         generate_span.set_attribute("runner.animal", animal)

#         # Check if the animal is a string
#         if not isinstance(animal, str):
#             return jsonify({"error": "The animal must be a string"}), 400
        
#         animal = str(animal).strip().lower()

#         # Check if the animal contains any digits
#         if any(char.isdigit() for char in animal):
#             error_message = "The animal name must not contain numbers."
#             generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
#             generate_span.record_exception(Exception(error_message))
#             return jsonify({"error": error_message}), 400

#         if animal == "snorblefox":
#             error_message = f"The animal '{animal}' does not exist."
#             try:
#                 raise ValueError(error_message)
#             except Exception as e:
#                 generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
#                 generate_span.record_exception(e)
#             logging.warning(error_message)
#             return jsonify({"error": error_message}), 400
        
#         # Sleep for 5 seconds if the animal is a goat
#         if animal == "goat":
#             with tracer.start_span("sleep_timer") as sleep_span:
#                 sleep_duration = 5
#                 sleep_span.set_attribute("sleep.duration_seconds", sleep_duration)
#                 time.sleep(sleep_duration)

#         # Get a fact about the animal
#         fact_response = requests.post("http://fact-generator:5001/generate", json={"animal": animal})
#         fact = fact_response.json().get("result")
#         generate_span.set_attribute("fact_generator.fact", fact)
#         logging.info(f"Generated fact for {animal}: {fact}")

#         # # Get an image of the animal
#         # image_response = requests.post("http://image-generator:5002/generate", json={"prompt": fact})
#         # image_url = image_response.json().get("result")
#         # generate_span.set_attribute("image_generator.image_url", image_url)
#         # logging.info(f"Generated image for {animal}: {image_url}")
#         # return jsonify({"animal": animal, "fact": fact, "image_url": image_url})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)