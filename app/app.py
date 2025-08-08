from flask import Flask, Blueprint, render_template
import pandas as pd
import os
from flask_cors import CORS
# from main.routes import main_blueprint
# from barnes_and_noble.routes import barnes_and_noble_blueprint
# from p_and_e_rollup_match.routes import p_and_e_blueprint

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "www.library.tufts.edu"}})

# app.register_blueprint(main_blueprint)
# app.register_blueprint(barnes_and_noble_blueprint, url_prefix="/barnes_and_noble")
# app.register_blueprint(p_and_e_blueprint, url_prefix="/p_and_e")
if __name__ == "__main__":
    app.run(debug=True)
