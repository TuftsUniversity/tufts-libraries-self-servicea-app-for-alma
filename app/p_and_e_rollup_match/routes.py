from flask import Blueprint, request, redirect, url_for, send_file, current_app
from werkzeug.utils import secure_filename
import os
from .p_and_e_rollup_match import ResourceMatch

p_and_e_blueprint = Blueprint("p_and_e", __name__)


@p_and_e_blueprint.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return redirect(url_for("main.error"))
    file = request.files["file"]
    if file.filename == "":
        return redirect(url_for("main.error"))
    filename = secure_filename(file.filename)
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    isbn_bool = request.form.get("isbn_bool", "no").lower() in ["1", "yes", "y"]
    matcher = ResourceMatch(file_path, isbn_bool)
    output_path = matcher.process()
    return send_file(output_path, as_attachment=True)
