from flask import Flask, Blueprint, render_template
import pandas as pd
import os
from routes import main

app = Flask(__name__)




app = Flask(__name__)

app.register_blueprint(main)
if __name__ == "__main__":
    app.run(debug=True)
