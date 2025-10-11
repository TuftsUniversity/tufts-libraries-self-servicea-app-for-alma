from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    send_file,
    current_app,
    render_template,
    jsonify, 
    session 
)

from werkzeug.utils import secure_filename
import os
from .barnes_and_noble import OverlapAnalysis
from .auth_barnes_and_noble import login_required
from .auth_barnes_and_noble import verify_token_or_reject
from flask_cors import CORS, cross_origin
from flask import current_app, send_from_directory
barnes_and_noble_blueprint = Blueprint("barnes_and_noble", __name__)


# Serve component.js
@barnes_and_noble_blueprint.route('/component.js')
@cross_origin()
def serve_component():

    component_path = os.path.join(current_app.root_path, 'barnes_and_noble')
    return send_from_directory(component_path, 'component.js', mimetype='application/javascript')

# Serve component-template
@barnes_and_noble_blueprint.route('/component-template')
@cross_origin()
def serve_component_template():


    return render_template("barnes_and_noble.html", is_component=True)


@barnes_and_noble_blueprint.route("/upload", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", headers=["Content-Type", "Authorization"])

def upload_file():

    if "file" not in request.files:
        return redirect(url_for("main.error"))
    is_component = request.form.get('isComponent')

    print(is_component)
    if is_component == 'false':
        if 'user' not in session:
            return redirect(url_for('barnes_and_noble_auth.login', _scheme="https", _external=True))

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
    analysis = OverlapAnalysis(file)
    output_path = analysis.process()
    return send_file(
        output_path,
        as_attachment=True,
        download_name="Updated_Barnes_and_Noble.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@barnes_and_noble_blueprint.route("/", methods=["GET"])
@login_required
def index():
    return render_template("barnes_and_noble.html")
