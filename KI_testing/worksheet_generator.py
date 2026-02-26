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
    """Generate a worksheet from selected topics and nested question types."""
    
    syllabus_data = load_syllabus(grade, subject)
    if not syllabus_data:
        print(f"No syllabus found. Run syllabus-analyzer.py first!")
        return None
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    chart_counter = {'bar': 0, 'pie': 0, 'line': 0}
    section_instructions = []
    
    for idx, block in enumerate(question_blocks, 1):
        is_continuous = block.get('continuous', False)
        
        if 'subtopic_id' in block:
            subtopic = find_subtopic_by_id(syllabus_data, block['subtopic_id'])
            topic_name = subtopic['name'] if subtopic else "Practice Problems"
        else:
            topic_name = block.get('topic_name', "Practice Problems")
        
        section_instructions.append(f"\n--- SECTION {idx} START ---")
        # Removed the <h2> header output line
        
        chart_types = ['bar_chart', 'pie_chart', 'line_chart', 'data_table']
        visual_types = chart_types + ['draw_shapes', 'identify_shapes', 'partition_shapes', 'area_perimeter_grid', 'tell_time', 'draw_time', 'number_line']
        
        # Support both old flat structures and new nested sub_blocks
        sub_blocks = block.get('sub_blocks', [{'type': block.get('type', 'short_answer'), 'count': block.get('count', 1)}])
        
        if is_continuous:
            # Look for a visual type to anchor the context
            visual_types_in_block = [sb['type'] for sb in sub_blocks if sb['type'] in visual_types]
            base_visual = visual_types_in_block[0] if visual_types_in_block else None
            
            if base_visual:
                extra_chart_info = ""
                if base_visual == 'pie_chart':
                    chart_id = f"piechart_{chart_counter['pie']}"
                    chart_counter['pie'] += 1
                    extra_chart_info = f" (Use Google pie chart with id='{chart_id}')"
                elif base_visual == 'line_chart':
                    chart_id = f"linechart_{chart_counter['line']}"
                    chart_counter['line'] += 1
                    extra_chart_info = f" (Use Google line chart with id='{chart_id}')"
                    
                section_instructions.append(f"Output: Create EXACTLY ONE {base_visual} drawing/plot/chart{extra_chart_info} about '{topic_name}'. Design it so it contains enough data/detail to warrant multiple questions.")
            else:
                section_instructions.append(f"Output: Create ONE shared reading passage, word-problem scenario, or mathematical context about '{topic_name}'.")
                
            section_instructions.append("Output: THEN, directly below that single shared scenario/visual, generate the following distinct numbered questions:")
            
            total_q = 0
            for sb in sub_blocks:
                sb_type = sb['type']
                sb_count = sb.get('count', 1)
                
                if sb_type in visual_types:
                    section_instructions.append(f"Output: Generate EXACTLY {sb_count} distinct questions (using the 'short_answer' format) that ask the student to analyze the drawing/plot.")
                else:
                    section_instructions.append(f"Output: Generate EXACTLY {sb_count} {sb_type} question(s) based strictly on that single shared scenario.")
                total_q += sb_count
                
            section_instructions.append(f"STOP AFTER EXACTLY {total_q} QUESTION(S) - DO NOT ADD MORE")
            
        else:
            # Discrete - loop through each sub_block separately
            total_q = 0
            for sb in sub_blocks:
                sb_type = sb['type']
                sb_count = sb.get('count', 1)
                
                if sb_type in visual_types:
                    extra_chart_info = ""
                    if sb_type == 'pie_chart':
                        chart_id = f"piechart_{chart_counter['pie']}"
                        chart_counter['pie'] += 1
                        extra_chart_info = f" (Use Google pie chart with id='{chart_id}')"
                    elif sb_type == 'line_chart':
                        chart_id = f"linechart_{chart_counter['line']}"
                        chart_counter['line'] += 1
                        extra_chart_info = f" (Use Google line chart with id='{chart_id}')"
                        
                    section_instructions.append(f"Output: Create EXACTLY {sb_count} completely separate problems about '{topic_name}'.")
                    section_instructions.append(f"Output: For EACH problem, you MUST generate BOTH a NEW {sb_type} drawing/plot{extra_chart_info} AND an actual question/prompt attached to it.")
                else:
                    section_instructions.append(f"Output: Generate EXACTLY {sb_count} separate and independent {sb_type} question(s) about '{topic_name}'.")
                total_q += sb_count
                
            section_instructions.append(f"STOP AFTER EXACTLY {total_q} QUESTION(S) - DO NOT ADD MORE")
            
        section_instructions.append(f"--- SECTION {idx} END ---\n")
    
    # Calculate total problems dynamically through sub-blocks for grading header
    total_problems = sum(
        sb.get('count', 1) 
        for block in question_blocks 
        for sb in block.get('sub_blocks', [{'count': block.get('count', 1)}])
    )
    
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
        
        worksheets_dir = Path('worksheets')
        worksheets_dir.mkdir(exist_ok=True)
        
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in worksheet_title)
        safe_title = safe_title.replace(' ', '_').lower()
        output_file = worksheets_dir / f'grade{grade}_{safe_title}.html'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(" Worksheet generated successfully!")
        print(f" Saved to: {output_file}")
        return html_content
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None