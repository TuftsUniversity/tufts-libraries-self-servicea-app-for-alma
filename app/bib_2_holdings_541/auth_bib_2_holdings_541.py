# app/bib_2_holdings_541/auth_bib_2_holdings_541.py

from flask import Blueprint, request, redirect, url_for, render_template, session, flash
from functools import wraps
import jwt
import os
import json
from dotenv import load_dotenv

print("AUTH541 IMPORTED FROM:", __file__, flush=True)
print("AUTH541 IMPORT CWD:", os.getcwd(), flush=True)

# ✅ Blueprint name MUST match all url_for() references:
#    url_for("auth_bib_2_holdings_541.login") etc.
bib_2_holdings_541_auth_blueprint = Blueprint("auth_bib_2_holdings_541", __name__)

load_dotenv()

credentials_list = json.loads(os.getenv("CREDENTIALS_541", "[]"))


def check_credentials(username, password):
    return any(
        c.get("username") == username and c.get("password") == password
        for c in credentials_list
    )


@bib_2_holdings_541_auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if check_credentials(username, password):
            session["user"] = username
            return redirect(url_for("bib_2_holdings_541.index", _scheme="https", _external=True))

        flash("Invalid username or password", "error")
        return redirect(url_for("auth_bib_2_holdings_541.login", _scheme="https", _external=True))

    return render_template("login.html")


@bib_2_holdings_541_auth_blueprint.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("auth_bib_2_holdings_541.login", _scheme="https", _external=True))


def login_required(f):
    """Decorator to protect routes that require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth_bib_2_holdings_541.login", _scheme="https", _external=True))
        return f(*args, **kwargs)
    return decorated_function


def verify_token_or_reject():
    print("AUTH541 VERIFY RUNNING FROM:", __file__, flush=True)
    print("AUTH541 VERIFY CWD:", os.getcwd(), flush=True)
    auth_header = request.headers.get("Authorization")
    print("🚨 Authorization header received:", auth_header)

    if not auth_header or not auth_header.startswith("Bearer "):
        return False, "Missing or invalid Authorization header."

    token = auth_header.split(" ", 1)[1].strip()
    public_key_path = os.getenv("PUBLIC_KEY_PATH", "public.pem")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    public_key_path = os.path.join(BASE_DIR, public_key_path)
    #print(f"🔐 Verifying token using public key at: {public_key_path} current working directory is { os.getcwd()}", flush=True)
    try:
        with open(public_key_path, "rb") as key_file:
            public_key = key_file.read()
        print("🔑 Public key loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load public key: {e}  🔐 Verifying token using public key at: {public_key_path}. Current working directory is { os.getcwd()}")
        return False, "Server configuration error."

    try:
        header = jwt.get_unverified_header(token)
        print("🔍 JWT header:", header)

        decoded = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        print("✅ Token decoded successfully:", decoded)
        return True, "authorized"

    except jwt.InvalidAlgorithmError as e:
        print(f"Invalid algorithm: {e}")
        return False, f"Algorithm not supported: {e}"

    except jwt.InvalidSignatureError:
        print("Invalid signature the token doesn't match this public key")
        return False, "Invalid signature."

    except jwt.ExpiredSignatureError:
        print("Token expired.")
        return False, "Token expired."

    except jwt.InvalidTokenError as e:
        print("Invalid token:", str(e))
        return False, f"Invalid token: {str(e)}"
