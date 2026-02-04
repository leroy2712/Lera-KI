import requests
import json
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load .env file
env_path = Path('.env')
load_dotenv(dotenv_path=env_path)

# Load prompts from YAML
prompts_path = Path('prompts.yaml')
with open(prompts_path, 'r', encoding='utf-8') as f:
    PROMPTS = yaml.safe_load(f)

def grade_worksheet(grade, subject, worksheet_title, student_answers, answer_key=None):
    """
    Grade a student's worksheet using LLM.
    
    Args:
        grade (int): Grade level
        subject (str): Subject name
        worksheet_title (str): Title/topic of worksheet
        student_answers (str): Raw text of student answers
        answer_key (str, optional): Correct answers if available
    
    Returns:
        dict: Grading results with scores and feedback
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # Format prompt with grading instructions
    prompt = PROMPTS['grading']['system_prompt'].format(
        grade=grade,
        subject=subject,
        worksheet_title=worksheet_title,
        student_answers=student_answers,
        answer_key=answer_key if answer_key else "No answer key provided - use your knowledge to verify correctness"
    )
    
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    model_params = PROMPTS['grading']['model_params']
    
    data = {
        "model": "google/gemma-3-27b-it:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": model_params['temperature'],
        "max_tokens": model_params['max_tokens']
    }
    
    print(f"Grading Grade {grade} {subject} worksheet: {worksheet_title}...")
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        
        # Remove markdown code blocks if present
        if content.startswith('```'):
            content = content.split('```', 2)[1]
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()
        
        try:
            grading_data = json.loads(content)
            
            # Add metadata
            grading_data['metadata'] = {
                'graded_at': datetime.now().isoformat(),
                'tokens_used': result['usage']['total_tokens'],
                'grade_level': grade,
                'subject': subject,
                'worksheet_title': worksheet_title
            }
            
            # Calculate costs
            input_cost = (result['usage']['prompt_tokens'] / 1_000_000) * 0.040
            output_cost = (result['usage']['completion_tokens'] / 1_000_000) * 0.150
            total_cost = input_cost + output_cost
            
            print(f"✅ Grading complete!")
            print(f"Score: {grading_data['score']}/{grading_data['total_questions']} ({grading_data['percentage']}%)")
            print(f"Tokens used: {result['usage']['total_tokens']}")
            print(f"Cost: ${total_cost:.6f}")
            
            return grading_data
            
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse JSON response")
            print(f"Response: {content[:500]}")
            return None
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

def save_grading_result(grading_data, student_name=None):
    """Save grading results to JSON file."""
    Path('gradings').mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    student_part = f"_{student_name.replace(' ', '_')}" if student_name else ""
    filename = f"gradings/grading_{grading_data['metadata']['grade_level']}_{timestamp}{student_part}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(grading_data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved grading results to {filename}")
    return filename

if __name__ == "__main__":
    # Test example
    sample_answers = """
1. 5 + 3 = 8
2. 12 - 7 = 5
3. 15 - 8 = 6
4. Word Problem: Sarah has 10 apples. She gives 4 to her friend. How many does she have left?
   Answer: 6 apples
5. 20 + 15 = 35
    """
    
    sample_key = """
1. 8
2. 5
3. 7
4. 6 apples
5. 35
    """
    
    result = grade_worksheet(
        grade=3,
        subject="Math",
        worksheet_title="Addition and Subtraction Practice",
        student_answers=sample_answers,
        answer_key=sample_key
    )
    
    if result:
        save_grading_result(result, student_name="Test Student")
