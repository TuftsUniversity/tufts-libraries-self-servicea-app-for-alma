# app/bib_2_holdings_541/routes.py

from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    current_app,
    render_template,
    send_from_directory,
    session,
    jsonify,
)
from werkzeug.utils import secure_filename
from flask_cors import cross_origin

import os
import uuid
from redis import Redis
from rq import Queue

from .auth_bib_2_holdings_541 import verify_token_or_reject
from .tasks import run_bib2holdings541_job


blueprint_541 = Blueprint("bib_2_holdings_541", __name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
UPLOAD_FOLDER = os.getenv("BIB2HOLDINGS541_UPLOAD_FOLDER", "/tmp/bib2holdings541_uploads")
RESULTS_DIR = os.getenv("BIB2HOLDINGS541_RESULTS_DIR", "/tmp/bib2holdings541_results")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


def get_queue():
    redis_conn = Redis.from_url(REDIS_URL)
    return Queue("bib2holdings541", connection=redis_conn)


def _truthy(v: str) -> bool:
    return (v or "").strip().lower() in ("true", "1", "yes", "y", "on")


def is_component_request() -> bool:
    # Uploads will send isComponent in form-data; page loads should use querystring ?isComponent=true
    return _truthy(request.form.get("isComponent")) or _truthy(request.args.get("isComponent"))


def require_auth_or_reject():
    """
    Component -> JWT Authorization header
    Browser   -> Flask session
    """
    if is_component_request():
        ok, message = verify_token_or_reject()
        if not ok:
            return jsonify({"error": message}), 401
        return None

    if "user" not in session:
        wants_json = "application/json" in (request.headers.get("Accept") or "")
        if wants_json:
            return jsonify({"error": "Not authenticated"}), 401
        return redirect(url_for("auth_bib_2_holdings_541.login", _scheme="https", _external=True))

    return None


# ----------------------------------------------------------------------
# Static assets for web component
# ----------------------------------------------------------------------

@blueprint_541.route("/component.js")
@cross_origin()
def serve_component():
    component_path = os.path.join(current_app.root_path, "bib_2_holdings_541")
    return send_from_directory(component_path, "component.js", mimetype="application/javascript")


@blueprint_541.route("/component-template")
@cross_origin()
def serve_component_template():
    # component-template is meant to be embedded, so treat it as component mode
    return render_template("bib_2_holdings_541.html", is_component=True)


# ----------------------------------------------------------------------
# Upload -> enqueue RQ job
# ----------------------------------------------------------------------

@blueprint_541.route("/upload", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", headers=["Content-Type", "Authorization"])
def upload_file():

    print("UPLOAD_FILE ROUTE HIT", flush=True)
    print("method =", request.method, flush=True)
    print("form keys =", list(request.form.keys()), flush=True)
    print("args =", dict(request.args), flush=True)
    print("headers auth present =", bool(request.headers.get("Authorization")), flush=True)
    # CORS preflight must succeed without auth headers
    if request.method == "OPTIONS":
        return ("", 204)
    is_component = request.form.get('isComponent')
    if is_component == 'false':
        if 'user' not in session:
            return redirect(url_for('barnes_and_noble_auth.login', _scheme="https", _external=True))

    else:




        # Verify token first
        is_verified, message_or_userid = verify_token_or_reject()
        if not is_verified:
            return jsonify({"error": message_or_userid}), 401

        #return redirect(url_for("main.error"))
    auth_response = require_auth_or_reject()
    if auth_response:
        return auth_response

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    email = (request.form.get("email") or "").strip()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    email_as_attachment = _truthy(request.form.get("email_as_attachment"))

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file selected"}), 400

    job_id = str(uuid.uuid4())
    safe_name = secure_filename(file.filename) or "input.txt"
    saved_path = os.path.join(UPLOAD_FOLDER, f"{job_id}__{safe_name}")
    file.save(saved_path)

    if not os.path.exists(saved_path) or os.path.getsize(saved_path) == 0:
        return jsonify({"error": f"Upload save failed: {saved_path}"}), 500

    q = get_queue()
    q.enqueue(
        run_bib2holdings541_job,
        kwargs={
            "job_id": job_id,
            "input_path": saved_path,
            "email": email,
            "email_as_attachment": email_as_attachment,
        },
        job_timeout=60 * 60,
        result_ttl=7 * 24 * 3600,
    )

    return jsonify({"status": "queued", "job_id": job_id})


# ----------------------------------------------------------------------
# Download results (browser session only)
# ----------------------------------------------------------------------

@blueprint_541.route("/results/<path:filename>", methods=["GET"])
def download_result(filename):
    if "user" not in session:
        return redirect(url_for("auth_bib_2_holdings_541.login", _scheme="https", _external=True))
    return send_from_directory(RESULTS_DIR, filename, as_attachment=True)


# ----------------------------------------------------------------------
# Main UI
# ----------------------------------------------------------------------

@blueprint_541.route("/", methods=["GET"])
def index():
    # For a normal browser load, this uses session auth
    # For component loads, use ?isComponent=true (GET has no form-data)
    auth_response = require_auth_or_reject()
    if auth_response:
        return auth_response

    return render_template("bib_2_holdings_541.html", is_component=is_component_request())
