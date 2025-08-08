
from flask import Blueprint, request, redirect, url_for, render_template, session, flash, jsonify
from functools import wraps

import os
import json
import jwt
from dotenv import load_dotenv
import hmac
blueprint_auth_541 = Blueprint('auth_p_to_e', __name__)

    # Hardcoded credentials

load_dotenv()
credentials = json.loads(os.getenv("CREDENTIALS_P_TO_E"))
USERNAME = credentials["username"]
PASSWORD = credentials["password"]

key = os.getenv("KEY")

@blueprint_auth_541.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == USERNAME and password == PASSWORD:
            session['user'] = username
            return redirect(url_for('bib_2_holdings_541.index', _scheme="https", _external=True))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('auth_541.login', _scheme="https", _external=True))

    return render_template('login.html')

@blueprint_auth_541.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('auth_541.login', _scheme="https", _external=True))

def verify_signature(message, key, expected):

    sha256_hash_digest = hmac.new(bytes(expected, encoding='utf-8'), msg=bytes(key, encoding='utf-8'), digestmod=hashlib.sha256).hexdigest()

    # construct response data with base64 encoded hash
    # response = {
    # 'response_token': 'sha256=' + base64.b64encode(sha256_hash_digest)
    # }

    return_key = bytes(key, encoding='utf-8')
    # return [return_key, base64.b64encode(sha256_hash_digest)]
    return [return_key, sha256_hash_digest]

def login_required(f):
    """Decorator to protect routes that require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth_541.login', _scheme="https", _external=True))  # Redirect to the login page if not logged in
        return f(*args, **kwargs)
    return decorated_function

from flask import request
import jwt
import os

def verify_token_or_reject():
    auth_header = request.headers.get('Authorization')
    print("🚨 Authorization header received:", auth_header)

    if not auth_header or not auth_header.startswith('Bearer '):
        print("❌ Missing or malformed Authorization header")
        return False, "Missing or invalid Authorization header."

    token = auth_header.split(" ")[1]
    print("🧪 Extracted token:", token)

    # Load public key from environment or fallback
    public_key_path = os.getenv("PUBLIC_KEY_PATH", "public.pem")
    try:
        with open(public_key_path, "r") as key_file:
            public_key = key_file.read()
    except Exception as e:
        print(f"❌ Failed to load public key: {e}")
        return False, "Server configuration error."

    try:
        decoded = jwt.decode(token, public_key, algorithms=["RS256"])
        print("✅ Token decoded successfully:", decoded)
        return True, "authorized"

    except jwt.ExpiredSignatureError:
        print("❌ Token expired")
        return False, "Token expired. Please log in again."

    except jwt.InvalidTokenError as e:
        print("❌ Invalid token:", str(e))
        return False, f"Invalid token: {str(e)}"

