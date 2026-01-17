import requests
import json
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Load prompts from YAML
prompts_path = Path(__file__).parent / 'prompts.yaml'
with open(prompts_path, 'r', encoding='utf-8') as f:
    PROMPTS = yaml.safe_load(f)

def generate_worksheet(grade=3, topic="Addition and Subtraction", sections=None):
    if sections is None:
        sections = [
            {'name': 'Addition Practice', 'type': 'short_answer', 'count': 5},
            {'name': 'Word Problems', 'type': 'word_problem', 'count': 2}
        ]
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # Track chart IDs
    chart_counter = {'bar': 0, 'pie': 0, 'line': 0}
    
    # Build instructions by grouping sections
    section_instructions = []
    i = 0
    
    while i < len(sections):
        section = sections[i]
        item_type = section['type']
        name = section.get('name', '')
        count = section.get('count', 1)
        
        if item_type in ['bar_chart', 'pie_chart', 'line_chart', 'data_table']:
            grouped_section = [f"\n--- SECTION {i+1} START ---"]
            grouped_section.append(f"Output: <h2>{name or f'Chart {i+1}'}</h2>")
            
            if item_type == 'bar_chart':
                grouped_section.append("Output: CSS bar chart (5 bars)")
            elif item_type == 'pie_chart':
                chart_id = f"piechart_{chart_counter['pie']}"
                chart_counter['pie'] += 1
                grouped_section.append(f"Output: Google pie chart with id='{chart_id}' (4 items)")
            elif item_type == 'line_chart':
                chart_id = f"linechart_{chart_counter['line']}"
                chart_counter['line'] += 1
                grouped_section.append(f"Output: Google line chart with id='{chart_id}' (5 days)")
            elif item_type == 'data_table':
                grouped_section.append("Output: Data table (4 rows)")
            
            i += 1
            while i < len(sections) and not sections[i].get('name'):
                q_section = sections[i]
                q_type = q_section['type']
                q_count = q_section.get('count', 1)
                q_options = q_section.get('options', '')
                
                question_desc = f"{q_count} {q_type} questions"
                if q_options:
                    question_desc += f" ({q_options} options)"
                question_desc += f" - ABOUT THE CHART/TABLE ABOVE"
                
                grouped_section.append(f"Then output: {question_desc}")
                i += 1
            
            grouped_section.append(f"--- SECTION {i} END ---\n")
            section_instructions.extend(grouped_section)
            
        else:
            section_instructions.append(f"\n--- SECTION {i+1} START ---")
            section_instructions.append(f"Output: <h2>{name}</h2>")
            
            question_desc = f"{count} {item_type} questions"
            if 'options' in section:
                question_desc += f" ({section['options']} options)"
            if section.get('difficulty'):
                question_desc += f" [difficulty: {section['difficulty']}]"
            
            section_instructions.append(f"Output: {question_desc}")
            section_instructions.append(f"--- SECTION {i+1} END ---\n")
            i += 1
    
    total_problems = sum(s.get('count', 0) for s in sections if s['type'] not in ['data_table', 'bar_chart', 'pie_chart', 'line_chart'])
    
    # Load prompt from YAML and format
    prompt = PROMPTS['worksheet']['system_prompt'].format(
        grade=grade,
        topic=topic,
        section_instructions=''.join(section_instructions)
    )

    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    # Get model params from YAML
    model_params = PROMPTS['worksheet']['model_params']
    
    data = {
        "model": "google/gemma-3-27b-it:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": model_params['temperature'],
        "max_tokens": model_params['max_tokens']
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('html'):
                content = content[4:]
            content = content.strip()
        
        template_path = Path(__file__).parent / 'worksheet_template.html'
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        
        title = f"Grade {grade} Math Practice - {topic}"
        html_content = template.replace('{{TITLE}}', title)
        html_content = html_content.replace('{{CONTENT}}', content)
        html_content = html_content.replace('{{TOTAL_POINTS}}', str(total_problems))
        
        output_file = Path(__file__).parent / f'grade{grade}_worksheet.html'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print("✓ Worksheet generated successfully!")
        print(f"✓ Saved to: {output_file}")
        print(f"✓ Input tokens: {result['usage']['prompt_tokens']}")
        print(f"✓ Output tokens: {result['usage']['completion_tokens']}")
        print(f"✓ Total tokens: {result['usage']['total_tokens']}")
        
        input_cost = (result['usage']['prompt_tokens'] / 1_000_000) * 0.040
        output_cost = (result['usage']['completion_tokens'] / 1_000_000) * 0.150
        total_cost = input_cost + output_cost
        print(f"✓ Estimated cost: ${total_cost:.6f} (${total_cost*100:.4f}¢)")
        
        return html_content
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    api_key = os.getenv('OPENROUTER_API_KEY')
    
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in .env file")
    else:
        generate_worksheet(
            grade=4,
            topic="Complete Skills Assessment",
            sections=[
                {'name': '1. Addition Practice', 'type': 'short_answer', 'count': 5},
                {'name': '2. Bar Chart Analysis', 'type': 'bar_chart'},
                {'type': 'short_answer', 'count': 2},
                {'type': 'word_problem', 'count': 1},
                {'name': '3. Reading Data Tables', 'type': 'data_table'},
                {'type': 'short_answer', 'count': 2},
                {'type': 'multiple_choice', 'count': 2, 'options': 4},
                {'name': '4. Pie Chart Survey', 'type': 'pie_chart'},
                {'type': 'fill_in_blank', 'count': 3},
                {'type': 'true_false', 'count': 2},
                {'name': '5. Line Chart Analysis', 'type': 'line_chart'},
                {'type': 'short_answer', 'count': 2},
                {'type': 'word_problem', 'count': 1},
                {'name': '6. Story Problems', 'type': 'word_problem', 'count': 3},
                {'name': '7. Multiple Choice Quiz', 'type': 'multiple_choice', 'count': 5, 'options': 4},
                {'name': '8. True or False', 'type': 'true_false', 'count': 5},
                {'name': '9. Fill in the Blanks', 'type': 'fill_in_blank', 'count': 5},
                {'name': '10. Match the Problems', 'type': 'matching', 'count': 1},
                {'name': '11. Show Your Work', 'type': 'show_your_work', 'count': 3},
                {'name': '12. Number Line Practice', 'type': 'number_line', 'count': 3},
                {'name': '13. Put in Order', 'type': 'ordering', 'count': 3},
                {'name': '14. Circle the Answer', 'type': 'circle_correct', 'count': 5}
            ]
        )
