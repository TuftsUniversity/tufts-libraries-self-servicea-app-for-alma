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
from flask_cors import CORS, cross_origin
from flask import current_app, send_from_directory

from app.p_and_e_rollup_match.auth_p_to_e import verify_token_or_reject


p_and_e_blueprint = Blueprint("p_and_e", __name__)
CORS(p_and_e_blueprint, resources={r"/*": {"origins": "*"}})
from app.p_and_e_rollup_match.p_and_e_rollup_match import ResourceMatch

# Serve component.js
@p_and_e_blueprint.route('/component.js')
@cross_origin()
def serve_component():

    component_path = os.path.join(current_app.root_path, 'p_and_e_rollup_match')
    return send_from_directory(component_path, 'component.js', mimetype='application/javascript')
# Serve component-template
@p_and_e_blueprint.route('/component-template')
@cross_origin()

def serve_component_template():


    return render_template("p_and_e_rollup_match.html", is_component=True)


@p_and_e_blueprint.route('/upload', methods=["POST", "OPTIONS"])
@cross_origin(origins="*", headers=["Content-Type", "Authorization"])
def upload_file():
    # ✅ Verify token first
    is_verified, message_or_userid = verify_token_or_reject()
    if not is_verified:
        return jsonify({"error": message_or_userid}), 401

    file = request.files.get("file")

    if not file:
        return "No file provided", 400

    isbn_bool = request.form.get("isbn_bool", "false").lower() == "true"

    resource_match = ResourceMatch(file, isbn_bool)
    return resource_match.process()


# Upload processing
#@p_and_e_blueprint.route('/upload', methods=["POST"])
#@cross_origin()
#def upload_file():
    #request_data = request.headers.get('Authorization')
    #print(request_data)
    #print("abc test")

    #file = request.files.get("file")
    #if not file:
        #return "No file provided", 400

    #isbn_bool = request.form.get("isbn_bool", "false").lower() == "true"

    #resource_match = ResourceMatch(file, isbn_bool)
    #return resource_match.process()

# Normal access
@p_and_e_blueprint.route('/', methods=["GET"])
@cross_origin()

def index():
    return render_template("p_and_e_rollup_match.html", is_component=False)
