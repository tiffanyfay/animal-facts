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
    with tracer.start_as_current_span("fact_generator") as generate_span:
        data = request.get_json()
        animal = data.get("animal")
        if not animal:
            return jsonify({"error": "You must provide an animal"}), 400

        # Set span attributes
        generate_span.set_attribute("fact_generator.animal", animal)

        # Create a prompt using the provided animal value.
        prompt = f"Tell me an interesting fact about {animal}."
        generate_span.set_attribute("fact_generator.prompt", prompt)

        model = "gpt-3.5-turbo"
        generate_span.set_attribute("fact_generator.model", model)

        try:
            # Print environment variables to debug
            # print("OpenAI Environment:", {k:v for k,v in os.environ.items() if 'OPENAI' in k or 'PROXY' in k})
            
            # Create a span for the OpenAI API call
            with tracer.start_span("openai_request") as openai_span:
                client = OpenAI(
                    # This is the default and can be omitted
                    api_key=os.environ.get("OPENAI_API_KEY"),
                )
                response = client.responses.create(
                    model=model,
                    instructions="You are an assistant that provides interesting facts about animals.",
                    input=prompt
                )
                fact = response.output_text
                generate_span.set_attribute("fact_generator.fact", fact)
            return jsonify({"result": fact})
        
        except Exception as e:
            # Record error in span
            generate_span.record_exception(e)
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            
            # Print the full error traceback
            import traceback
            print("Error traceback:", traceback.format_exc())
            openai_span.set_attribute("error.message", str(e))
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)