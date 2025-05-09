# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, send_file
import os
import uuid
from pathlib import Path
from eda_generator import parse_input, generate_eda_xml, create_eda_file, create_eda_zip

app = Flask(__name__)
UPLOAD_FOLDER = "/tmp"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        f = request.files['file']
        ext = f.filename.split('.')[-1].lower()
        if ext not in ['csv', 'json']:
            return "Nur CSV oder JSON erlaubt.", 400
        unique_name = str(uuid.uuid4())
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_name}.{ext}")
        f.save(input_path)
        data = parse_input(input_path)
        tree = generate_eda_xml(data)
        zip_path = create_eda_zip(tree, unique_name)
        return send_file(zip_path, as_attachment=True)
    return render_template('index.html')