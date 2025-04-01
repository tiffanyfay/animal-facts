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
def generate():
    # Create a new span for the generate endpoint
    with tracer.start_as_current_span("generate_fact") as generate_span:
        data = request.get_json()
        animal = data.get("animal")
        if not animal:
            return jsonify({"error": "You must provide an animal"}), 400

        # Set span attributes
        generate_span.set_attribute("animal", animal)

        # Create a prompt using the provided animal value.
        prompt = f"Tell me an interesting fact about {animal}."

        try:
            # Print environment variables to debug
            # print("OpenAI Environment:", {k:v for k,v in os.environ.items() if 'OPENAI' in k or 'PROXY' in k})
            
            # Create a span for the OpenAI API call
            with tracer.start_span("openai_completion") as openai_span:
                # Initialize client with explicit empty proxy configuration
                # client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                client = OpenAI(
                    # This is the default and can be omitted
                    api_key=os.environ.get("OPENAI_API_KEY"),
                )
                response = client.responses.create(
                    model="gpt-4o",
                    instructions="You are an assistant that provides interesting facts about animals.",
                    input=prompt
                )

                # response = client.chat.completions.create(
                #     model="gpt-3.5-turbo",
                #     messages=[
                #         {
                #             "role": "system",
                #             "content": "You are an assistant that provides interesting facts about animals."
                #         },
                #         {
                #             "role": "user",
                #             "content": prompt
                #         }
                #     ],
                #     max_tokens=150,
                #     temperature=0.7
                # )
                # Get the generated fact
                # result = response.output_text
                # openai_span.set_attribute("completion_tokens", len(result.split()))
                
            return jsonify({"result": response.output_text})
        except Exception as e:
            # Record error in span
            generate_span.record_exception(e)
            generate_span.set_status(trace.Status(trace.StatusCode.ERROR))
            
            # Print the full error traceback
            import traceback
            print("Error traceback:", traceback.format_exc())
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)