from flask import Blueprint, request, redirect, url_for, render_template, session, flash, jsonify
from functools import wraps
import os
import json
import jwt
import hmac
from dotenv import load_dotenv

auth_barnes_and_noble_blueprint = Blueprint("auth_barnes_and_noble", __name__)

load_dotenv()
credentials = json.loads(os.getenv("CREDENTIALS_BARNES_AND_NOBLE"))
USERNAME = credentials["username"]
PASSWORD = credentials["password"]

key = os.getenv("KEY")

@auth_barnes_and_noble_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == USERNAME and password == PASSWORD:
            session["user"] = username
            return redirect(url_for("barnes_and_noble.index", _scheme="https", _external=True))
        else:
            flash("Invalid username or password", "error")
            return redirect(url_for("auth_barnes_and_noble.login", _scheme="https", _external=True))

    return render_template("login.html")

@auth_barnes_and_noble_blueprint.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("auth_barnes_and_noble.login", _scheme="https", _external=True))

def verify_token_or_reject():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False, "Missing or invalid Authorization header."

    token = auth_header.split(" ")[1]

    public_key_path = os.getenv("PUBLIC_KEY_PATH", "public.pem")
    try:
        with open(public_key_path, "r") as key_file:
            public_key = key_file.read()
    except Exception as e:
        return False, "Server configuration error."

    try:
        decoded = jwt.decode(token, public_key, algorithms=["RS256"])
        return True, "authorized"

    except jwt.ExpiredSignatureError:
        return False, "Token expired. Please log in again."

    except jwt.InvalidTokenError as e:
        return False, f"Invalid token: {str(e)}"

def login_required(f):
    """Decorator to protect routes that require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth_barnes_and_noble.login", _scheme="https", _external=True))
        return f(*args, **kwargs)
    return decorated_function