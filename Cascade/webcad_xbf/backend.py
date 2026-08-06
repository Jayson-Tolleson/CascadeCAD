import os
import glob

def find_flask_app():
    # Look for common Flask entry points
    candidates = ['app.py', 'server.py', 'main.py', 'wsgi.py']
    for c in candidates:
        if os.path.exists(c):
            return c
    # Fallback to any python file containing Flask initialization
    for py_file in glob.glob('*.py'):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'Flask' in content:
                    return py_file
        except Exception:
            continue
    return None

def apply_patch():
    target_file = find_flask_app()
    if not target_file:
        print("Error: Could not locate the Flask backend Python file.")
        return

    print(f"Found Flask application file: {target_file}")

    with open(target_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if route already exists
    if '/api/import' in content:
        print("The /api/import route is already present in the backend file.")
        return

    # Define the route code to inject
    

@app.route('/api/import', methods=['POST'])
def api_import():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file part in request'}), 400
            
        file = request.files['file']
        project_name = request.form.get('project_name', 'Imported Assembly')
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No selected file'}), 400
            
        upload_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'projects'))
        os.makedirs(upload_dir, exist_ok=True)
        
        filename = file.filename
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        return jsonify({
            'success': True, 
            'message': f'Model {filename} imported successfully.',
            'project_name': project_name,
            'file_path': file_path
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/projects', methods=['GET'])
def list_projects():
    try:
        upload_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'projects'))
        os.makedirs(upload_dir, exist_ok=True)
        files = []
        for filename in os.listdir(upload_dir):
            file_path = os.path.join(upload_dir, filename)
            if os.path.isfile(file_path):
                files.append({
                    'name': filename,
                    'path': file_path,
                    'size': os.path.getsize(file_path)
                })
        return jsonify({'success': True, 'projects': files}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<path:filename>', methods=['GET'])
def get_project_file(filename):
    try:
        upload_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'projects'))
        return send_from_directory(upload_dir, filename)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 404
