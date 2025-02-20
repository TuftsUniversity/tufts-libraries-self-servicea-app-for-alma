from flask import Flask, Blueprint, render_template
import pandas as pd
import os


app = Flask(__name__)


main_blueprint = Blueprint('main', __name__)


@main_blueprint.route('/')
def index():
    return render_template('upload.html')

@main_blueprint.route('/success')
def success():
    return "File processed successfully!"

@main_blueprint.route('/error')
def error():
    return "An error occurred during processing."



if __name__ == "__main__":
    app.run(debug=True)
