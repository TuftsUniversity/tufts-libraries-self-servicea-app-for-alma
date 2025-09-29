
from flask import Blueprint, request, redirect, url_for, render_template, session, flash
from functools import wraps

import os
import json
from dotenv import load_dotenv
barnes_and_noble_auth_blueprint = Blueprint('barnes_and_noble_auth', __name__)

    # Hardcoded credentials

load_dotenv()
credentials = json.loads(os.getenv("CREDENTIALS_BARNES_AND_NOBLE"))


credentials_list = json.loads(os.getenv("CREDENTIALS_BARNES_AND_NOBLE"))

def check_credentials(username, password):
    return any(c["username"] == username and c["password"] == password for c in credentials_list)
@barnes_and_noble_auth_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if check_credentials(username, password):


            session['user'] = username
            return redirect(url_for('barnes_and_noble.index', _scheme="https", _external=True))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('barnes_and_noble_auth.login', _scheme="https", _external=True))

    return render_template('login.html')

@barnes_and_noble_auth_blueprint.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('barnes_and_noble_auth.login', _scheme="https", _external=True))


def login_required(f):
    """Decorator to protect routes that require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('barnes_and_noble_auth.login', _scheme="https", _external=True))  # Redirect to the login page if not logged in
        return f(*args, **kwargs)
    return decorated_function

def verify_token_or_reject():
    auth_header = request.headers.get('Authorization')
    print("ðŸš¨ Authorization header received:", auth_header)

    if not auth_header or not auth_header.startswith('Bearer '):
        print("âŒ Missing or malformed Authorization header")
        return False, "Missing or invalid Authorization header."

    token = auth_header.split(" ")[1]
    print("ðŸ§ª Extracted token:", token)

    # Load public key from environment or fallback
    public_key_path = os.getenv("PUBLIC_KEY_PATH", "public.pem")
    try:
        with open(public_key_path, "r") as key_file:
            public_key = key_file.read()
    except Exception as e:
        print(f"âŒ Failed to load public key: {e}")
        return False, "Server configuration error."

    try:
        decoded = jwt.decode(token, public_key, algorithms=["RS256"])
        print("âœ… Token decoded successfully:", decoded)
        return True, "authorized"

    except jwt.ExpiredSignatureError:
        print("âŒ Token expired")
        return False, "Token expired. Please log in again."

    except jwt.InvalidTokenError as e:
        print("âŒ Invalid token:", str(e))
        return False, f"Invalid token: {str(e)}"
