import requests
import json
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from current directory
env_path = '.env'
load_dotenv(dotenv_path=env_path)

# Load prompts from YAML
prompts_path = 'prompts.yaml'
with open(prompts_path, 'r', encoding='utf-8') as f:
    PROMPTS = yaml.safe_load(f)

def analyze_syllabus(syllabus_text, grade, subject="Math", save_to_file=True):
    """
    Analyze a syllabus and extract structured topics/subtopics.
    
    Args:
        syllabus_text (str): The raw syllabus text
        grade (int): Grade level (e.g., 3, 4, 5)
        subject (str): Subject name (e.g., "Math", "Science")
        save_to_file (bool): Whether to save output to JSON file
    
    Returns:
        dict: Structured syllabus data
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # Format prompt with syllabus text
    prompt = PROMPTS['syllabus_analyzer']['system_prompt'].format(
        syllabus_text=syllabus_text,
        grade=grade,
        subject=subject
    )
    
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    # Get model params from YAML
    model_params = PROMPTS['syllabus_analyzer']['model_params']
    
    data = {
        "model": "google/gemma-3-27b-it:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": model_params['temperature'],
        "max_tokens": model_params['max_tokens']
    }
    
    print(f"Analyzing syllabus for Grade {grade} {subject}...")
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        
        # Remove markdown code blocks if present
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()
        
        try:
            syllabus_data = json.loads(content)
            
            # Add metadata
            syllabus_data['_metadata'] = {
                'analyzed_at': __import__('datetime').datetime.now().isoformat(),
                'tokens_used': result['usage']['total_tokens']
            }
            
            if save_to_file:
                # Save to JSON file
                output_file = f'syllabus/syllabus_grade{grade}_{subject.lower()}.json'
                
                # Create directory if it doesn't exist
                Path('syllabus').mkdir(exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(syllabus_data, f, indent=2, ensure_ascii=False)
                
                print(f"Syllabus analyzed successfully!")
                print(f"Saved to: {output_file}")
                print(f"Found {len(syllabus_data['topics'])} main topics")
                total_subtopics = sum(len(topic['subtopics']) for topic in syllabus_data['topics'])
                print(f"Found {total_subtopics} subtopics")
            
            print(f"Tokens used: {result['usage']['total_tokens']}")
            
            # Calculate cost
            input_cost = (result['usage']['prompt_tokens'] / 1_000_000) * 0.040
            output_cost = (result['usage']['completion_tokens'] / 1_000_000) * 0.150
            total_cost = input_cost + output_cost
            print(f"Cost: ${total_cost:.6f}")
            
            return syllabus_data
            
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse JSON response")
            print(f"Response: {content[:500]}")
            return None
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None


def load_analyzed_syllabus(grade, subject="Math"):
    """Load a previously analyzed syllabus from file."""
    syllabus_file = f'syllabus/syllabus_grade{grade}_{subject.lower()}.json'
    
    if not Path(syllabus_file).exists():
        print(f"No analyzed syllabus found for Grade {grade} {subject}")
        return None
    
    with open(syllabus_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_topics(syllabus_data):
    """Pretty print all topics and subtopics from analyzed syllabus."""
    print(f"\nGrade {syllabus_data['grade']} {syllabus_data['subject']} Syllabus\n")
    
    for topic_idx, topic in enumerate(syllabus_data['topics'], 1):
        print(f"{topic_idx}. {topic['name']}")
        for subtopic in topic['subtopics']:
            print(f"   • {subtopic['name']} [{subtopic.get('difficulty', 'medium')}]")
            if subtopic.get('description'):
                print(f"     → {subtopic['description']}")
        print()


if __name__ == "__main__":
    # Example usage
    sample_syllabus = """
Numbers and Operations
adding and subtracting within 1,000
place value of ones, tens and hundreds
rounding numbers to the nearest 10 or 100
relationship between addition and subtraction
introduction to multiplication
introduction to division
multiply and divide within 100
fractions as parts of a whole

Geometry
classification of shapes by their properties
partitioning of shapes into equal parts
area and perimeter of irregular shapes by counting squares
area and perimeter of rectangles

Measurement and Data
telling time to the nearest minute
measuring length, mass, and volume
representing data using bar graphs and pictographs
solving problems using information from graphs
"""
    
    # Analyze the syllabus
    syllabus_data = analyze_syllabus(
        syllabus_text=sample_syllabus,
        grade=3,
        subject="Math"
    )
    
    if syllabus_data:
        # Display the structured topics
        list_topics(syllabus_data)
