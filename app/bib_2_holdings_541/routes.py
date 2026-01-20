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

from werkzeug.utils import secure_filename
import os
from app.bib_2_holdings_541.bib_2_holdings_541 import Bib2Holdings541
from flask_cors import CORS, cross_origin
from .auth_bib_2_holdings_541 import login_required
from .auth_bib_2_holdings_541 import verify_token_or_reject
# routes.py
import uuid
from datetime import datetime
from rq import Queue
from redis import Redis


blueprint_541 = Blueprint("bib_2_holdings_541", __name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
UPLOAD_FOLDER = os.getenv("BIB2HOLDINGS541_UPLOAD_FOLDER", "/tmp/bib2holdings541_uploads")
upload_dir = UPLOAD_FOLDER  # from env: BIB2HOLDINGS541_UPLOAD_FOLDER

if (os.path.isdir(UPLOAD_FOLDER)):
    upload_dir = UPLOAD_FOLDER
else:
    os.makedirs(upload_dir, exist_ok=True)

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





def get_queue():
    redis_conn = Redis.from_url(REDIS_URL)
    return Queue("bib2holdings541", connection=redis_conn)

@blueprint_541.route("/upload", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", headers=["Content-Type", "Authorization"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    is_component = request.form.get("isComponent")
    if is_component == "true":
        is_verified, message_or_userid = verify_token_or_reject()
        if not is_verified:
            return jsonify({"error": message_or_userid}), 401
    else:
        if "user" not in session:
            wants_json = "application/json" in (request.headers.get("Accept") or "")
            if "user" not in session:
                if wants_json:
                    return jsonify({"error": "Not authenticated"}), 401
                return redirect(url_for("...login..."))


    email = (request.form.get("email") or "").strip()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    email_as_attachment = (request.form.get("email_as_attachment") or "").lower() == "true"

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Save upload to disk (job needs a persistent path)
    upload_dir = current_app.config.get("UPLOAD_FOLDER", "/tmp/bib2holdings541_uploads")
    os.makedirs(upload_dir, exist_ok=True)

    job_id = str(uuid.uuid4())
    safe_name = secure_filename(file.filename) or "input.txt"
    saved_path = os.path.join(upload_dir, f"{job_id}__{safe_name}")
    file.save(saved_path)


    if not os.path.exists(saved_path) or os.path.getsize(saved_path) == 0:
        return jsonify({"error": f"Upload save failed: {saved_path}"}), 500

    q = get_queue()
    q.enqueue(
        "app.bib_2_holdings_541.tasks.run_bib2holdings541_job",
        job_id=job_id,
        input_path=saved_path,
        email=email,
        email_as_attachment=email_as_attachment,
        job_timeout=60 * 60,   # 1 hour
        result_ttl=7 * 24 * 3600
    )

    return jsonify({"status": "queued", "job_id": job_id})


@blueprint_541.route("/results/<path:filename>", methods=["GET"])
@login_required
def download_result(filename):
    results_dir = os.getenv("BIB2HOLDINGS541_RESULTS_DIR", "/tmp/bib2holdings541_results")
    return send_from_directory(results_dir, filename, as_attachment=True)


@blueprint_541.route("/", methods=["GET"])
def index():
    is_component = request.form.get("isComponent")
    if is_component == "true":
        is_verified, message_or_userid = verify_token_or_reject()
        if not is_verified:
            return jsonify({"error": message_or_userid}), 401

        else:
            return render_template("bib_2_holdings_541.html", is_component=True)
    else:
        if "user" not in session:
            wants_json = "application/json" in (request.headers.get("Accept") or "")
            if "user" not in session:
                if wants_json:
                    return jsonify({"error": "Not authenticated"}), 401
                return redirect(url_for("auth_bib_2_holdings_541.login"))
        else:
            return render_template("bib_2_holdings_541.html", is_component=False)
 
    
