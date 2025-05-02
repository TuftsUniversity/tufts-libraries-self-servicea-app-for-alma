from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    send_file,
    current_app,
    render_template,
)
from werkzeug.utils import secure_filename
import os
from .p_and_e_rollup_match import ResourceMatch
from flask_cors import CORS
p_and_e_blueprint = Blueprint("p_and_e", __name__)


@p_and_e_blueprint.route('/component.js')
def serve_component():
    return send_file("p_and_e_rollup_match/component.js", mimetype="application/javascript")

@p_and_e_blueprint.route('/component-template')
def serve_component_template():
    return render_template("p_and_e_rollup_match.html")  # Template stored in app/templates/


@p_and_e_blueprint.route("/upload", methods=["POST"])
def upload_file():
    if request.method == "POST":
        # Retrieve the file from the form field named 'file'
        file = request.files.get("file")
        if not file:
            return "No file provided", 400

        # Optional: Check for additional form fields, e.g., a checkbox for ISBN processing
        isbn_bool = request.form.get("isbn_bool", "false").lower() == "true"

        resource_match = ResourceMatch(file, isbn_bool)
        return resource_match.process()
    else:
        # Render a simple upload form (ensure you have an 'upload.html' template)
        return render_template("upload.html")


@p_and_e_blueprint.route("/", methods=["GET"])
def index():
    return render_template("p_and_e_rollup_match.html")
