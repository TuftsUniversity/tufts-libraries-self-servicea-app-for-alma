from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    send_file,
    current_app,
    render_template,
)
from app.bib_2_holdings_541.auth_541 import login_required
from werkzeug.utils import secure_filename
import os
from app.bib_2_holdings_541.bib_2_holdings_541 import Bib2Holdings541
from flask_cors import CORS, cross_origin

blueprint_541 = Blueprint("bib_2_holdings_541", __name__)


@blueprint_541.route("/upload", methods=["POST"])
@login_required
def upload_file():
    if request.method == "POST":
        # Retrieve the file from the form field named 'file'
        file = request.files.get("file")
        if not file:
            return "No file provided", 400

        bib2Holdings541 = Bib2Holdings541(file.stream)

        return bib2Holdings541.process()
    else:
        # Render a simple upload form (ensure you have an 'upload.html' template)
        return render_template("upload.html")


@blueprint_541.route("/", methods=["GET"])
@login_required
def index():
    return render_template("bib_2_holdings_541.html")
