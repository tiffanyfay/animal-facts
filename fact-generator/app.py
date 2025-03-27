from flask import Flask, request, jsonify
import requests
import os
import logging
import openai
from opentelemetry import trace

# Acquire a tracer
tracer = trace.get_tracer("combined.tracer")

app = Flask(__name__)

# Set your OpenAI API key from an environment variable
openai.api_key = os.environ.get("OPENAI_API_KEY")


@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    animal = data.get("animal")
    if not animal:
        return jsonify({"error": "Missing 'animal' in request body"}), 400

    # Create a prompt using the provided animal value.
    prompt = f"Tell me an interesting fact about {animal}."

    try:
        # Print environment variables to debug
        print("OpenAI Environment:", {k:v for k,v in os.environ.items() if 'OPENAI' in k or 'PROXY' in k})
        
        # Initialize client with explicit empty proxy configuration
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant that provides interesting facts about animals."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=150,
            temperature=0.7
        )
        # Extract the generated message from the assistant
        result = response.choices[0].message.content.strip()
        return jsonify({"result": result})
    except Exception as e:
        # Print the full error traceback
        import traceback
        print("Error traceback:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)