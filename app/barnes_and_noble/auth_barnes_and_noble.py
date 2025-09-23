
from flask import Blueprint, request, redirect, url_for, render_template, session, flash
from functools import wraps

import os
import json
from dotenv import load_dotenv
barnes_and_noble_auth_blueprint = Blueprint('barnes_and_noble_auth_blueprint', __name__)

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
            return redirect(url_for('auth_barnes_and_noble.login', _scheme="https", _external=True))

    return render_template('login.html')

@barnes_and_noble_auth_blueprint.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('auauth_barnes_and_nobleth_541.login', _scheme="https", _external=True))


def login_required(f):
    """Decorator to protect routes that require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth_barnes_and_noble.login', _scheme="https", _external=True))  # Redirect to the login page if not logged in
        return f(*args, **kwargs)
    return decorated_function
