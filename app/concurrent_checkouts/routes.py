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
    jsonify,
)
from flask_cors import CORS, cross_origin
from werkzeug.utils import secure_filename
import os
import jwt
from .concurrent_checkouts import ConcurrentCheckouts
from .auth_concurrent_checkouts import login_required, verify_token_or_reject  # optional if you plan to protect routes

# Blueprint definition
concurrent_checkouts_blueprint = Blueprint("concurrent_checkouts", __name__)
CORS(concurrent_checkouts_blueprint)

# Optional: Serve component.js if you have one
@concurrent_checkouts_blueprint.route("/component.js")
@cross_origin()
def serve_component():
    component_path = os.path.join(current_app.root_path, "concurrent_checkouts")
    return send_from_directory(component_path, "component.js", mimetype="application/javascript")


# Optional: Serve component template
@concurrent_checkouts_blueprint.route("/component-template")
@cross_origin()
def serve_component_template():
    return render_template("concurrent_checkouts.html", is_component=True)


# Main upload route — mirrors 541 pattern closely
@concurrent_checkouts_blueprint.route("/upload", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", headers=["Content-Type", "Authorization"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    # is_component = request.form.get("isComponent")
    # if is_component == "false":
    #     # Optional login requirement if using session
    #     if "user" not in session:
    #         return redirect(url_for("concurrent_checkouts_auth.login", _scheme="https", _external=True))
    # else:
    #     # Verify token if using API calls with JWT
    #     is_verified, message_or_userid = verify_token_or_reject()
    #     if not is_verified:
    #         return jsonify({"error": message_or_userid}), 401

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    upload_path = os.path.join(current_app.config.get("UPLOAD_FOLDER", "./uploads"), filename)
    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
    file.save(upload_path)

    # Instantiate and process
    cc = ConcurrentCheckouts()
    try:
        cc.process_file(upload_path)
        output_path = os.path.join("./Output", "Counts.xlsx")
        return send_file(output_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Basic index route — browser upload form
@concurrent_checkouts_blueprint.route("/", methods=["GET"])
def index():
    return render_template("concurrent_checkouts.html")
