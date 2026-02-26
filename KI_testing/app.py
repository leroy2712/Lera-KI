from flask import Flask, render_template, request, jsonify, send_file
import json
from pathlib import Path
from syllabus_analyzer import analyze_syllabus, load_analyzed_syllabus
from worksheet_generator import generate_worksheet
import base64
from worksheet_grader import grade_worksheet_vision, save_grading_result
import PyPDF2
import docx
import io
import re

app = Flask(__name__)

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# Syllabus analyzer page
@app.route('/syllabus')
def syllabus_page():
    return render_template('syllabus.html')

#API: Get present syllabuses (demo only)
@app.route('/api/syllabuses')
def api_list_syllabuses():
    syllabus_dir = Path('syllabus')
    if not syllabus_dir.exists():
        return jsonify({'syllabuses': []})
    
    syllabuses = []
    for file in syllabus_dir.glob('syllabus_grade*.json'):
        # Extract grade and subject from filename: syllabus_grade3_math.json
        match = re.search(r'syllabus_grade(\d+)_(.+)\.json', file.name)
        if match:
            grade = int(match.group(1))
            subject = match.group(2).capitalize()
            syllabuses.append({
                'grade': grade,
                'subject': subject,
                'filename': file.name,
                'display_name': f"Grade {grade} {subject}"
            })
            
    # Sort so they appear in a logical order (e.g., Grade 1, Grade 2...)
    syllabuses = sorted(syllabuses, key=lambda x: (x['grade'], x['subject']))
    return jsonify({'syllabuses': syllabuses})

# API: Analyze syllabus
@app.route('/api/analyze-syllabus', methods=['POST'])
def api_analyze_syllabus():
    # Because we switched to FormData, we use request.form and request.files
    grade = request.form.get('grade')
    subject = request.form.get('subject', 'Math')
    syllabus_text = request.form.get('syllabus_text', '')
    
    # Handle File Upload
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            try:
                # Extract text from PDF
                if file.filename.lower().endswith('.pdf'):
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
                    extracted_text = ""
                    for page in pdf_reader.pages:
                        extracted_text += page.extract_text() + "\n"
                    syllabus_text = extracted_text
                
                # Extract text from DOCX
                elif file.filename.lower().endswith('.docx'):
                    doc = docx.Document(io.BytesIO(file.read()))
                    syllabus_text = "\n".join([para.text for para in doc.paragraphs])
                
                # Extract text from TXT
                elif file.filename.lower().endswith('.txt'):
                    syllabus_text = file.read().decode('utf-8')
            except Exception as e:
                return jsonify({'error': f'Failed to read file: {str(e)}'}), 400

    if not syllabus_text or not grade:
        return jsonify({'error': 'Missing syllabus text or file'}), 400
    
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
        grade = request.form.get('grade')
        subject = request.form.get('subject')
        worksheet_title = request.form.get('worksheet_title')
        answer_key = request.form.get('answer_key')
        
        # Get list of all uploaded files under the 'student_images' key
        image_files = request.files.getlist('student_images')
        
        if not image_files or image_files[0].filename == '':
            return jsonify({'success': False, 'error': 'No image(s) uploaded'}), 400
            
        # Convert all uploaded images to base64 dictionaries
        encoded_images = []
        for img in image_files:
            image_bytes = img.read()
            encoded_images.append({
                "base64": base64.b64encode(image_bytes).decode('utf-8'),
                "mime_type": img.mimetype
            })
        
        # Call the vision grader with the list of encoded images
        result = grade_worksheet_vision(
            grade=int(grade),
            subject=subject,
            worksheet_title=worksheet_title,
            images=encoded_images, # Replaced single image args with this list
            answer_key=answer_key
        )
        
        if result:
            student_name = request.form.get('student_name', 'student')
            save_grading_result(result, student_name)
            return jsonify({'success': True, 'data': result})
        else:
            return jsonify({'success': False, 'error': 'Failed to grade worksheet. The AI model may be overloaded, please try again.'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Ensure directories exist
    Path('syllabus').mkdir(exist_ok=True)
    Path('worksheets').mkdir(exist_ok=True)
    
    app.run(host='0.0.0.0', debug=True, port=5000)