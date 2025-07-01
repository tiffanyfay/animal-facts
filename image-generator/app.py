from flask import Flask, request, jsonify
import requests
import os
import logging
from openai import OpenAI
from opentelemetry import trace

# Acquire a tracer
tracer = trace.get_tracer("combined.tracer")

app = Flask(__name__)


@app.route('/', methods=['POST'])
def generate():
    # Create a new span
    with tracer.start_as_current_span("image_generator") as generate_span:
        data = request.get_json()
        prompt = data.get("prompt")
        if not prompt:
            return jsonify({"error": "You must provide a prompt"}), 400

        # Set span attributes
        generate_span.set_attribute("image_generator.prompt", prompt)

        try:
            # Create a span for the OpenAI API call
            with tracer.start_span("openai_request") as openai_span:
                client = OpenAI(
                    api_key=os.environ.get("OPENAI_API_KEY"),
                )

                # Set generation parameters based on environment variables, falling back to defaults if blank
                model = os.environ.get("DALL_E_MODEL") or "dall-e-2"  # or "dall-e-3" 
                size = os.environ.get("DALL_E_SIZE") or "1024x1024"    # Available sizes: 256x256, 512x512, or 1024x1024
                # quality = os.environ.get("DALL_E_QUALITY") or "standard"  # or "hd" for DALL-E 3
                
                response = client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size,
                    n=1  # Number of images to generate
                )

                # Get the generated image URL
                image_url = response.data[0].url
                generate_span.set_attribute("image_generator.image_url", image_url)

                post_image(prompt, image_url)

            return jsonify({"result": image_url})
        except Exception as e:
            # Record error in span
            generate_span.record_exception(e)
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            
            # Print the full error traceback
            import traceback
            print("Error traceback:", traceback.format_exc())
            openai_span.set_attribute("error.message", str(e))
            return jsonify({"error": str(e)}), 500

def post_image(prompt, image_url):
    logging.info(f"Posting image to database for prompt '{prompt}': {image_url}")
    requests.post(
        "http://image-database:8080/images",
        data={"prompt": prompt, "url": image_url}
    )
    logging.info(f"Image posted to database for prompt '{prompt}': {image_url}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)