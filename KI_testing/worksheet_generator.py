import requests
import json
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = '.env'
load_dotenv(dotenv_path=env_path)

# Load prompts from YAML
prompts_path = 'prompts.yaml'
with open(prompts_path, 'r', encoding='utf-8') as f:
    PROMPTS = yaml.safe_load(f)


def load_syllabus(grade, subject="Math"):
    """Load analyzed syllabus for topic selection."""
    syllabus_file = f'syllabus/syllabus_grade{grade}_{subject.lower()}.json'
    
    if not Path(syllabus_file).exists():
        return None
    
    with open(syllabus_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_subtopic_by_id(syllabus_data, subtopic_id):
    """Find a subtopic by its ID."""
    for topic in syllabus_data['topics']:
        for subtopic in topic['subtopics']:
            if subtopic['id'] == subtopic_id:
                return subtopic
    return None


def generate_worksheet(grade, worksheet_title, question_blocks, subject="Math"):
    """
    Generate a worksheet from selected topics and question types.
    
    Args:
        grade (int): Grade level
        worksheet_title (str): Title for the worksheet
        question_blocks (list): List of question block configurations
            Example:
            [
                {
                    'subtopic_id': 'num_ops_1',  # from analyzed syllabus
                    'type': 'short_answer',
                    'count': 5,
                    'difficulty': 'easy'
                },
                {
                    'subtopic_id': 'geo_shapes_1',
                    'type': 'multiple_choice',
                    'count': 3,
                    'options': 4
                }
            ]
        subject (str): Subject name
    
    Returns:
        str: Generated HTML content
    """
    
    # Load syllabus to get topic names
    syllabus_data = load_syllabus(grade, subject)
    if not syllabus_data:
        print(f"No syllabus found. Run syllabus-analyzer.py first!")
        return None
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # Track chart IDs
    chart_counter = {'bar': 0, 'pie': 0, 'line': 0}
    
    # Build section instructions from question blocks
    section_instructions = []
    sections = []  # Track for token counting
    
    for idx, block in enumerate(question_blocks, 1):
        item_type = block['type']
        count = block.get('count', 1)
        
        # Get topic name from syllabus
        if 'subtopic_id' in block:
            subtopic = find_subtopic_by_id(syllabus_data, block['subtopic_id'])
            topic_name = subtopic['name'] if subtopic else "Practice Problems"
        else:
            topic_name = block.get('topic_name', "Practice Problems")
        
        # Handle charts
        if item_type in ['bar_chart', 'pie_chart', 'line_chart', 'data_table']:
            grouped_section = [f"\n--- SECTION {idx} START ---"]
            grouped_section.append(f"Output: <h2>{idx}. {topic_name}</h2>")
            
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
            
            grouped_section.append(f"--- SECTION {idx} END ---\n")
            section_instructions.extend(grouped_section)
            
        else:
            # Regular question section
            section_instructions.append(f"\n--- SECTION {idx} START ---")
            section_instructions.append(f"Output: <h2>{idx}. {topic_name}</h2>")

            # Make instructions VERY explicit
            question_desc = f"Output EXACTLY {count} {item_type} question(s)"
            if count == 1:
                question_desc = f"Output EXACTLY ONE {item_type} question"
                
            question_desc += f" about '{topic_name}'"

            # Add specific format reminder for problematic types
            if item_type in ['draw_time', 'tell_time']:
                question_desc += f" - USE ONLY THE {item_type.upper()} FORMAT, NO WORD PROBLEMS"
                
            if 'options' in block:
                question_desc += f" ({block['options']} options)"
            if block.get('difficulty'):
                question_desc += f" [difficulty: {block['difficulty']}]"

            section_instructions.append(f"Output: {question_desc}")
            section_instructions.append(f"STOP AFTER {count} QUESTION(S) - DO NOT ADD MORE")
            section_instructions.append(f"--- SECTION {idx} END ---\n")

        sections.append(block)
    
    total_problems = sum(b.get('count', 0) for b in question_blocks if b['type'] not in ['data_table', 'bar_chart', 'pie_chart', 'line_chart'])
    
    # Format prompt
    prompt = PROMPTS['worksheet']['system_prompt'].format(
        grade=grade,
        topic=worksheet_title,
        section_instructions=''.join(section_instructions)
    )
    
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    model_params = PROMPTS['worksheet']['model_params']
    
    data = {
        "model": "google/gemma-3-27b-it:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": model_params['temperature'],
        "max_tokens": model_params['max_tokens']
    }
    
    print(f"Generating worksheet: {worksheet_title}")
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('html'):
                content = content[4:]
            content = content.strip()
        
        template_path = 'templates/worksheet_template.html'
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        
        title = f"Grade {grade} {subject} - {worksheet_title}"
        html_content = template.replace('{{TITLE}}', title)
        html_content = html_content.replace('{{CONTENT}}', content)
        html_content = html_content.replace('{{TOTAL_POINTS}}', str(total_problems))
        
        # Create worksheets subdirectory if it doesn't exist
        worksheets_dir = Path('worksheets')
        worksheets_dir.mkdir(exist_ok=True)
        
        # Generate filename from title
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in worksheet_title)
        safe_title = safe_title.replace(' ', '_').lower()
        output_file = worksheets_dir / f'grade{grade}_{safe_title}.html'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(" Worksheet generated successfully!")
        print(f" Saved to: {output_file}")
        print(f" Input tokens: {result['usage']['prompt_tokens']}")
        print(f" Output tokens: {result['usage']['completion_tokens']}")
        print(f" Total tokens: {result['usage']['total_tokens']}")
        
        input_cost = (result['usage']['prompt_tokens'] / 1_000_000) * 0.040
        output_cost = (result['usage']['completion_tokens'] / 1_000_000) * 0.150
        total_cost = input_cost + output_cost
        print(f" Estimated cost: ${total_cost:.6f} (${total_cost*100:.4f}¢)")
        
        return html_content
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None


if __name__ == "__main__":
    # Example: Generate a custom worksheet using analyzed syllabus
    
    # First, make sure you've run syllabus-analyzer.py to generate the JSON
    
    # Define question blocks (teacher selects these)
    question_blocks = [
        {
            'subtopic_id': 'num_ops_add_sub',  # This would come from syllabus JSON
            'topic_name': 'Adding and Subtracting within 1,000',  # Fallback if no syllabus
            'type': 'short_answer',
            'count': 5,
            'difficulty': 'easy'
        },
        {
            'topic_name': 'Bar Chart Analysis',
            'type': 'bar_chart'
        },
        {
            'subtopic_id': 'num_ops_add_sub',
            'topic_name': 'Word Problems - Addition/Subtraction',
            'type': 'word_problem',
            'count': 3,
            'difficulty': 'medium'
        },
        {
            'subtopic_id': 'geo_shapes',
            'topic_name': 'Shape Classification',
            'type': 'multiple_choice',
            'count': 4,
            'options': 4
        }
    ]
    
    generate_worksheet(
        grade=3,
        worksheet_title="Mixed Review - Numbers and Shapes",
        question_blocks=question_blocks,
        subject="Math"
    )
