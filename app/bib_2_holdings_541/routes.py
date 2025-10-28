from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    send_file,
    current_app,
    render_template,
    send_from_directory,
    session,
    jsonify
)
from app.bib_2_holdings_541.auth_541 import login_required
from werkzeug.utils import secure_filename
import os
from app.bib_2_holdings_541.bib_2_holdings_541 import Bib2Holdings541
from flask_cors import CORS, cross_origin
from .auth_bib_2_holdings_541 import login_required
from .auth_bib_2_holdings_541 import verify_token_or_reject


blueprint_541 = Blueprint("bib_2_holdings_541", __name__)




# Serve component.js
@blueprint_541.route('/component.js')
@cross_origin()
def serve_component():

    component_path = os.path.join(current_app.root_path, 'bib_2_holdings_541')
    return send_from_directory(component_path, 'component.js', mimetype='application/javascript')

# Serve component-template
@blueprint_541.route('/component-template')
@cross_origin()
def serve_component_template():


    return render_template("bib_2_holdings_541.html", is_component=True)


@blueprint_541.route("/upload", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", headers=["Content-Type", "Authorization"])

def upload_file():

    if "file" not in request.files:
        return redirect(url_for("main.error"))
    is_component = request.form.get('isComponent')

    print(is_component)
    if is_component == 'false':
        if 'user' not in session:
            return redirect(url_for('bib_2_holdings_541_auth.login', _scheme="https", _external=True))

    else:


    

        # Verify token first
        is_verified, message_or_userid = verify_token_or_reject()
        if not is_verified:
            return jsonify({"error": message_or_userid}), 401

            #return redirect(url_for("main.error"))
    file = request.files.get("file")
    if file.filename == "":
        return redirect(url_for("main.error"))
    # filename = secure_filename(file.filename)
    # file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    # file.save(file_path)
    bib2Holdings541 = Bib2Holdings541(file.stream)

    return bib2Holdings541.process()



@blueprint_541.route("/", methods=["GET"])
@login_required
def index():
    return render_template("bib_2_holdings_541.html")

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

