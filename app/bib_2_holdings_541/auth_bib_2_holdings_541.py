
from flask import Blueprint, request, redirect, url_for, render_template, session, flash
from functools import wraps
import jwt
import os
import json
from dotenv import load_dotenv
bib_2_holdings_541_auth_blueprint = Blueprint('bib_2_holdings_541_auth', __name__)

    # Hardcoded credentials

load_dotenv()
credentials = json.loads(os.getenv("CREDENTIALS_541"))


credentials_list = json.loads(os.getenv("CREDENTIALS_541"))

def check_credentials(username, password):
    return any(c["username"] == username and c["password"] == password for c in credentials_list)
@bib_2_holdings_541_auth_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if check_credentials(username, password):


            session['user'] = username
            return redirect(url_for('bib_2_holdings_541.index', _scheme="https", _external=True))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('bib_2_holdings_541_auth.login', _scheme="https", _external=True))

    return render_template('login.html')

@bib_2_holdings_541_auth_blueprint.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('bib_2_holdings_541_auth.login', _scheme="https", _external=True))


def login_required(f):
    """Decorator to protect routes that require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('bib_2_holdings_541_auth.login', _scheme="https", _external=True))  # Redirect to the login page if not logged in
        return f(*args, **kwargs)
    return decorated_function


def verify_token_or_reject():
    auth_header = request.headers.get('Authorization')
    print("🚨 Authorization header received:", auth_header)

    if not auth_header or not auth_header.startswith('Bearer '):
        return False, "Missing or invalid Authorization header."

    token = auth_header.split(" ")[1]

    public_key_path = os.getenv("PUBLIC_KEY_PATH", "public.pem")

    try:
        with open(public_key_path, "rb") as key_file:  # ✅ open in binary mode
            public_key = key_file.read()
        print("🔑 Public key loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load public key: {e}")
        return False, "Server configuration error."

    try:
        header = jwt.get_unverified_header(token)
        print("🔍 JWT header:", header)

        # ✅ RS256 must match the key type — and public key must be PEM RSA
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False}
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
