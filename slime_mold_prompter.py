import json
import openai
import os
from dotenv import load_dotenv

load_dotenv()


def load_slime_mold_data(filename="slime_mold_data.json"):
    try:
        with open(filename, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error reading data: {e}")
        return []


def format_prompt(slime_data):
    prompts = []
    for entry in slime_data:
        prompts.append(
            f"The slime mold is moving {entry['growth_direction']} under "
            f"a light level of {entry['light_level']} at {entry['timestamp']}. "
            f"What might it be experiencing or thinking?"
        )
    return prompts

def get_llm_response(prompt):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error getting LLM response: {e}")
        return "Error in response"


if __name__ == "__main__":
    slime_mold_data = load_slime_mold_data()
    
    if slime_mold_data:
        prompts = format_prompt(slime_mold_data)
        
        for prompt in prompts:
            print(f"Prompt: {prompt}")
            response = get_llm_response(prompt)
            print(f"LLM Response: {response}\n")
