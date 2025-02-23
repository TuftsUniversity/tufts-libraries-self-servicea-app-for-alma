from flask import Blueprint, request, redirect, url_for, send_file, current_app
from werkzeug.utils import secure_filename
import os
from .barnes_and_noble import OverlapAnalysis

barnes_and_noble_blueprint = Blueprint("barnes_and_noble", __name__)


@barnes_and_noble_blueprint.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return redirect(url_for("main.error"))
    file = request.files["file"]
    if file.filename == "":
        return redirect(url_for("main.error"))
    filename = secure_filename(file.filename)
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)
    analysis = OverlapAnalysis(file_path)
    output_path = analysis.process()
    return send_file(output_path, as_attachment=True)
