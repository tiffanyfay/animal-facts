import time

from flask import Flask, request, jsonify
import requests
import os
import logging
from openai import OpenAI
from opentelemetry import trace

# Acquire a tracer
tracer = trace.get_tracer("combined.tracer")

app = Flask(__name__)

logger = logging.getLogger("image-generator")
logging.basicConfig(level=logging.INFO)

@app.route('/health', methods=['GET'])
def health():
    """
    Lightweight HTTP health endpoint that avoids calling OpenAI/DB.
    """
    start = time.time()
    with tracer.start_as_current_span("image_generator.health") as span:
        span.set_attribute("component", "image-generator")
        span.set_attribute("health.status", "ok")
        span.set_attribute("health.latency_ms", int((time.time() - start) * 1000))

    return jsonify({"service": "image-generator", "status": "ok"}), 200

STYLE_LOCK = """
Create one image:
- simple hand-drawn cartoon / sketch comic
- slightly sketchy dark outlines
- soft flat colors
- minimal shading
- clean centered composition
- no scenery, no gradients, no glow
- no words, no characters,no text, no labels, no extra characters 
- cute looking
"""

def build_image_prompt(raw_fact: str) -> str:
    return f"""{STYLE_LOCK}

Subject:
{raw_fact}

Output:
A single clean illustration that looks like part of the same animal type family.
"""

@app.route('/', methods=['POST'])
def generate():
    with tracer.start_as_current_span("image_generator") as generate_span:
        data = request.get_json()
        prompt = data.get("prompt")

        if not prompt:
            return jsonify({"error": "You must provide a prompt"}), 400

        # 🔹 Log original prompt
        logging.info("Received prompt", extra={"prompt.original": prompt})

        styled_prompt = build_image_prompt(prompt)

        # 🔹 Log transformed prompt
        logging.info("Styled prompt created", extra={
            "prompt.original": prompt,
            "prompt.styled": styled_prompt
        })

        # Add to tracing as well (nice for demo!)
        generate_span.set_attribute("image_generator.prompt.original", prompt)
        generate_span.set_attribute("image_generator.prompt.styled", styled_prompt)

        try:
            with tracer.start_span("openai_request") as openai_span:
                client = OpenAI(
                    api_key=os.environ.get("OPENAI_API_KEY"),
                )

                model = os.environ.get("DALL_E_MODEL") or "gpt-image-1"
                size = os.environ.get("DALL_E_SIZE") or "1024x1024"

                response = client.images.generate(
                    model=model,
                    prompt=styled_prompt,  # 👈 IMPORTANT: use styled prompt
                    size=size,
                    n=1
                )

                image_b64 = response.data[0].b64_json
                if not image_b64:
                    raise ValueError("OpenAI image response did not include base64 image data")
                image_url = f"data:image/png;base64,{image_b64}"

                # 🔹 Log result
                logging.info("Image generated", extra={
                    "prompt.original": prompt,
                    "image.response_type": "data_url",
                    "image.url_length": len(image_url)
                })

                generate_span.set_attribute("image_generator.image_response_type", "data_url")
                generate_span.set_attribute("image_generator.image_url_length", len(image_url))

                post_image(prompt, image_url)
                display_url = os.environ.get("IMAGE_DATABASE_DISPLAY_URL", "http://localhost:8080/images.html")

            return jsonify({"result": display_url, "image_saved": True})

        except Exception as e:
            generate_span.record_exception(e)
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))

            import traceback
            logging.error("Image generation failed: %s", str(e), extra={
                "prompt.original": prompt,
                "error": str(e),
                "traceback": traceback.format_exc()
            })

            return jsonify({"error": str(e)}), 500
def post_image(prompt, image_url):
    logging.info("Posting image to database", extra={
        "prompt.original": prompt,
        "image.url_length": len(image_url),
    })
    response = requests.post(
        "http://image-database:8080/images",
        json={"prompt": prompt, "url": image_url},
        timeout=10
    )
    response.raise_for_status()
    logging.info("Image posted to database", extra={"prompt.original": prompt})

if __name__ == '__main__':
    logger.info("Image Generator App Starting")
    app.run(host='0.0.0.0', port=5002)
