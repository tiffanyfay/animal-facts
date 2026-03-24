import time
import traceback
import os
import logging

from flask import Flask, request, jsonify
import requests
from openai import OpenAI
from opentelemetry import trace

# Acquire a tracer
tracer = trace.get_tracer("combined.tracer")

app = Flask(__name__)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)

def _preview(value, limit=120):
    if value is None:
        return "None"
    value = str(value)
    return value if len(value) <= limit else value[:limit] + "..."

@app.route('/health', methods=['GET'])
def health():
    start = time.time()
    logger.info("Health check received")

    with tracer.start_as_current_span("fact_generator.health") as span:
        span.set_attribute("component", "fact-generator")
        payload = {"service": "fact-generator", "status": "ok"}
        span.set_attribute("health.status", "ok")
        span.set_attribute("health.latency_ms", int((time.time() - start) * 1000))

    logger.info("Health check completed successfully")
    return jsonify(payload), 200

@app.route('/', methods=['POST'])
def generate():
    start = time.time()
    logger.info("Fact generation request received")

    with tracer.start_as_current_span("fact_generator") as generate_span:
        try:
            data = request.get_json(silent=True)
            if not data:
                logger.warning("Request body is missing or invalid JSON")
                return jsonify({"error": "Invalid or missing JSON body"}), 400

            animal = data.get("animal")
            logger.info("Incoming animal value: %s", _preview(animal))

            if not animal:
                logger.warning("No animal provided in request")
                return jsonify({"error": "You must provide an animal"}), 400

            generate_span.set_attribute("fact_generator.animal", animal)

            prompt = f"Tell me an interesting fact about {animal}."
            generate_span.set_attribute("fact_generator.prompt", prompt)
            logger.info("Built prompt: %s", _preview(prompt, 180))

            model = "gpt-3.5-turbo"
            generate_span.set_attribute("fact_generator.model", model)
            logger.info("Using model: %s", model)

            logger.info("Sending request to OpenAI Responses API")
            with tracer.start_span("openai_request") as openai_span:
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                response = client.responses.create(
                    model=model,
                    instructions="You are an assistant that provides interesting facts about animals.",
                    input=prompt
                )

                fact = response.output_text
                generate_span.set_attribute("fact_generator.fact", fact)

                logger.info("OpenAI response received; fact length=%d", len(fact) if fact else 0)
                openai_span.set_attribute("openai.response_length", len(fact) if fact else 0)

            elapsed_ms = int((time.time() - start) * 1000)
            logger.info("Fact generation completed in %d ms", elapsed_ms)
            return jsonify({"result": fact}), 200

        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.exception("Fact generation failed after %d ms", elapsed_ms)

            generate_span.record_exception(e)
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))

            try:
                openai_span.set_attribute("error.message", str(e))
            except Exception:
                pass

            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("Fact Generator App starting on 0.0.0.0:5001")
    app.run(host='0.0.0.0', port=5001)