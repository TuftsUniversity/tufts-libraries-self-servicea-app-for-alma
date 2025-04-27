from flask import Blueprint, request, redirect, url_for, send_file, current_app, render_template
from werkzeug.utils import secure_filename
import os
from .bib_to_holdings_541 import Update541

blueprint_541 = Blueprint("bib_2_holdings_541", __name__)


@blueprint_541.route("/upload", methods=["POST"])
def upload_file():
    if request.method == 'POST':
        # Retrieve the file from the form field named 'file'
        file = request.files.get('file')
        if not file:
            return "No file provided", 400

        # Optional: Check for additional form fields, e.g., a checkbox for ISBN processing
        isbn_bool = request.form.get('isbn_bool', 'false').lower() == 'true'

        resource_match = ResourceMatch(file, isbn_bool)
        return resource_match.process()
    else:
        # Render a simple upload form (ensure you have an 'upload.html' template)
        return render_template("upload.html")

@p_and_e_blueprint.route("/", methods=["GET"])
def index():
    return render_template("p_and_e_rollup_match.html")