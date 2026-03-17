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

HEALTH_TIMEOUT = 2.0  # seconds for each HTTP health probe

@app.route('/health', methods=['GET'])
def health_check():
    """
    HTTP health endpoint that calls downstream services' /health endpoints.
    Produces OTEL spans for each call so you can visualize them.
    """
    fact_url = os.environ.get("FACT_GENERATOR_HEALTH_URL", "http://fact-generator:5001/health")
    image_url = os.environ.get("IMAGE_GENERATOR_HEALTH_URL", "http://image-generator:5002/health")

    overall_ok = True
    results = {}

    # Helper to probe and record a span
    def probe(name: str, url: str):
        nonlocal overall_ok
        start = time.time()
        with tracer.start_as_current_span(f"runner.probe.{name}") as span:
            span.set_attribute("probe.url", url)
            try:
                resp = requests.get(url, timeout=HEALTH_TIMEOUT)
                latency_ms = int((time.time() - start) * 1000)
                span.set_attribute("probe.status_code", resp.status_code)
                span.set_attribute("probe.latency_ms", latency_ms)
                span.set_attribute("probe.ok", resp.ok)
                if resp.ok:
                    results[name] = {"ok": True, "status_code": resp.status_code, "latency_ms": latency_ms}
                    logger.info("Probe OK %s -> %s (%d ms)", name, url, latency_ms)
                    return True
                else:
                    overall_ok = False
                    body_snippet = (resp.text or "")[:500]
                    results[name] = {"ok": False, "status_code": resp.status_code, "body": body_snippet}
                    logger.warning("Probe FAIL %s -> %s status=%s body=%s", name, url, resp.status_code, body_snippet)
                    return False
            except requests.RequestException as e:
                overall_ok = False
                latency_ms = int((time.time() - start) * 1000)
                span.set_attribute("probe.error", str(e))
                span.set_attribute("probe.latency_ms", latency_ms)
                results[name] = {"ok": False, "error": str(e), "latency_ms": latency_ms}
                logger.error("Probe EXCEPT %s -> %s error=%s", name, url, str(e))
                return False

    probe("fact-generator", fact_url)
    probe("image-generator", image_url)

    # also attach an aggregate span attribute for the health check
    with tracer.start_as_current_span("runner.health.aggregate") as agg_span:
        agg_span.set_attribute("health.overall_ok", overall_ok)
        agg_span.set_attribute("health.results", str(results))

    status_code = 200 if overall_ok else 503
    return jsonify({"overall_ok": overall_ok, "results": results}), status_code



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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)