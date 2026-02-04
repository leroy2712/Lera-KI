from flask import Flask, render_template, request, jsonify, send_file
import json
from pathlib import Path
from syllabus_analyzer import analyze_syllabus, load_analyzed_syllabus
from worksheet_generator import generate_worksheet
from worksheet_grader import grade_worksheet, save_grading_result

app = Flask(__name__)

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# Syllabus analyzer page
@app.route('/syllabus')
def syllabus_page():
    return render_template('syllabus.html')

# API: Analyze syllabus
@app.route('/api/analyze-syllabus', methods=['POST'])
def api_analyze_syllabus():
    data = request.json
    syllabus_text = data.get('syllabus_text')
    grade = data.get('grade')
    subject = data.get('subject', 'Math')
    
    if not syllabus_text or not grade:
        return jsonify({'error': 'Missing syllabus text or grade'}), 400
    
    result = analyze_syllabus(syllabus_text, int(grade), subject, save_to_file=True)
    
    if result:
        return jsonify({
            'success': True,
            'data': result
        })
    else:
        return jsonify({'error': 'Failed to analyze syllabus'}), 500

# API: Load existing syllabus
@app.route('/api/load-syllabus/<int:grade>/<subject>')
def api_load_syllabus(grade, subject):
    syllabus_data = load_analyzed_syllabus(grade, subject)
    
    if syllabus_data:
        return jsonify({
            'success': True,
            'data': syllabus_data
        })
    else:
        return jsonify({'error': 'No syllabus found'}), 404

# Worksheet builder page
@app.route('/worksheet-builder')
def worksheet_builder():
    grade = request.args.get('grade', 3, type=int)
    subject = request.args.get('subject', 'Math')
    
    # Load syllabus
    syllabus_data = load_analyzed_syllabus(grade, subject)
    
    return render_template('worksheet_builder.html', 
                         grade=grade, 
                         subject=subject,
                         syllabus=syllabus_data)

# API: Generate worksheet
@app.route('/api/generate-worksheet', methods=['POST'])
def api_generate_worksheet():
    data = request.json
    grade = data.get('grade')
    worksheet_title = data.get('title')
    question_blocks = data.get('question_blocks')
    subject = data.get('subject', 'Math')
    
    if not all([grade, worksheet_title, question_blocks]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    result = generate_worksheet(int(grade), worksheet_title, question_blocks, subject)
    
    if result:
        return jsonify({
            'success': True,
            'message': 'Worksheet generated successfully'
        })
    else:
        return jsonify({'error': 'Failed to generate worksheet'}), 500

# API: List generated worksheets
@app.route('/api/worksheets')
def api_list_worksheets():
    worksheets_dir = Path('worksheets')
    if not worksheets_dir.exists():
        return jsonify({'worksheets': []})
    
    worksheets = []
    for file in worksheets_dir.glob('*.html'):
        worksheets.append({
            'filename': file.name,
            'path': str(file)
        })
    
    return jsonify({'worksheets': worksheets})

# View generated worksheet
@app.route('/view-worksheet/<filename>')
def view_worksheet(filename):
    worksheet_path = Path(f'worksheets/{filename}')
    if worksheet_path.exists():
        return send_file(worksheet_path)
    else:
        return "Worksheet not found", 404

@app.route('/grade')
def grade_interface():
    return render_template('grading_interface.html')

@app.route('/api/grade-worksheet', methods=['POST'])
def api_grade_worksheet():
    try:
        data = request.json
        
        result = grade_worksheet(
            grade=data['grade'],
            subject=data['subject'],
            worksheet_title=data['worksheet_title'],
            student_answers=data['student_answers'],
            answer_key=data.get('answer_key')
        )
        
        if result:
            # Optionally save the result
            if data.get('student_name'):
                save_grading_result(result, data['student_name'])
            
            return jsonify({'success': True, 'data': result})
        else:
            return jsonify({'success': False, 'error': 'Failed to grade worksheet'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Ensure directories exist
    Path('syllabus').mkdir(exist_ok=True)
    Path('worksheets').mkdir(exist_ok=True)
    
    app.run(debug=True, port=5000)