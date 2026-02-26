import requests
import json
import os
import base64
import yaml
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Load prompts from YAML
prompts_path = Path(__file__).parent / 'prompts.yaml'
with open(prompts_path, 'r', encoding='utf-8') as f:
    PROMPTS = yaml.safe_load(f)

def clean_json_response(content):
    """Safely extract JSON from the LLM's raw text response."""
    content = content.strip()
    if content.startswith('```'):
        lines = content.split('\n')
        # Fixed: check the first string in the list, not the list itself
        if lines.startswith('```'): lines = lines[1:]
        if lines[-1].startswith('```'): lines = lines[:-1]
        content = '\n'.join(lines)
    
    start_idx = content.find('{')
    end_idx = content.rfind('}')
    if start_idx != -1 and end_idx != -1:
        content = content[start_idx:end_idx + 1]
    return content

def grade_worksheet_vision(grade, subject, worksheet_title, images, answer_key=None):
    """
    Grades a multipage worksheet from a list of images using Nvidia Nemotron Nano 12B Vision,
    with automatic retries for dropped connections.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    if not answer_key or not answer_key.strip():
        answer_key = "Not provided. Evaluate correctness based on standard expectations."

    from string import Template
    prompt_template = Template(PROMPTS['grading_vision']['system_prompt'])
    prompt_text = prompt_template.safe_substitute(
        grade=grade,
        subject=subject,
        worksheet_title=worksheet_title,
        num_images=len(images), # Dynamically pass the number of images
        answer_key=answer_key
    )
    
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    model_params = PROMPTS['grading_vision']['model_params']
    
    # 1. Build the base message content with the text prompt
    message_content = [{"type": "text", "text": prompt_text}]
    
    # 2. Loop through all provided images and append them to the message content
    for img_data in images:
        message_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{img_data['mime_type']};base64,{img_data['base64']}"
            }
        })
    
    data = {
        "model": "nvidia/nemotron-nano-12b-v2-vl:free",
        "messages": [
            {
                "role": "user",
                "content": message_content
            }
        ],
        "temperature": model_params['temperature'],
        "max_tokens": model_params['max_tokens']
    }
    
    print(f"📝 Grading '{worksheet_title}' ({len(images)} pages) using Nemotron Nano 12B VL...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"🔄 Retrying API call (Attempt {attempt + 1}/{max_retries})...")
                
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            # 1. Check if OpenRouter returned an error inside the JSON
            if 'error' in result:
                error_msg = result['error'].get('message', 'Unknown API Error')
                error_code = result['error'].get('code')
                print(f"⚠️ OpenRouter API Error: {error_msg} (Code: {error_code})")
                
                # Retry on 502 Bad Gateway / Network connection lost
                if error_code in [502, 503, 429] and attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
                
            # 2. Check if 'choices' exists to prevent the KeyError
            if 'choices' not in result or len(result['choices']) == 0:
                print(f"❌ Unexpected API Response Format (No 'choices'):\n{json.dumps(result, indent=2)}")
                return None
                
            raw_content = result['choices'][0]['message']['content']
            
            cleaned_json_string = clean_json_response(raw_content)
            grading_data = json.loads(cleaned_json_string)
            
            # Inject metadata
            grading_data['metadata'] = {
                'model': 'nvidia/nemotron-nano-12b-v2-vl:free',
                'tokens_used': result['usage']['total_tokens'],
                'prompt_tokens': result['usage']['prompt_tokens'],
                'completion_tokens': result['usage']['completion_tokens'],
                'grade_level': grade,
                'subject': subject
            }
            
            print("✓ Grading completed successfully!")
            return grading_data
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Network/Request Error: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            if 'response' in locals() and response.text:
                print(f"Response Details: {response.text}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse LLM response as JSON. Error: {str(e)}")
            if 'raw_content' in locals():
                print(f"Raw Output:\n{raw_content}")
            return None
        except Exception as e:
            import traceback
            print(f"❌ Unexpected Error: {str(e)}")
            print(traceback.format_exc())
            return None
            
    print("❌ All API retry attempts failed.")
    return None

def save_grading_result(result_data, student_name="student"):
    results_dir = Path(__file__).parent / 'grading_results'
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in student_name)
    filename = f"grade_{safe_name}_{timestamp}.json"
    
    file_path = results_dir / filename
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=4)
        
    return str(file_path)
