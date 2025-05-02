
from flask import Blueprint, request, redirect, url_for, render_template, session, flash
from functools import wraps
import os
import json
from dotenv import load_dotenv
blueprint_auth_541 = Blueprint('auth_541', __name__)

    # Hardcoded credentials

load_dotenv()
credentials = json.loads(os.getenv("CREDENTIALS_541"))
USERNAME = credentials["username"]
PASSWORD = credentials["password"]

@blueprint_auth_541.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == USERNAME and password == PASSWORD:
            session['user'] = username
            return redirect(url_for('bib_2_holdings_541.index'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('auth_541.login'))

    return render_template('login.html')

@blueprint_auth_541.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('auth_541.login'))


def login_required(f):
    """Decorator to protect routes that require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth_541.login'))  # Redirect to the login page if not logged in
        return f(*args, **kwargs)
    return decorated_function
