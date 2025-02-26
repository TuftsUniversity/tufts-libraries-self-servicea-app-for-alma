from flask import Flask
from app.main import main_blueprint
from app.barnes_and_noble import barnes_and_noble_blueprint
from app.p_and_e_rollup_match import p_and_e_blueprint


def create_app():
    app = Flask(__name__)

    app.register_blueprint(main_blueprint)
    app.register_blueprint(barnes_and_noble_blueprint, url_prefix="/barnes_and_noble")
    app.register_blueprint(p_and_e_blueprint, url_prefix="/p_and_e")
    

    return app
