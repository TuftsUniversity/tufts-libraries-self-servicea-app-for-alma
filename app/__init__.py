from flask import Flask
from app.main import main_blueprint
from app.barnes_and_noble import barnes_and_noble_blueprint
from app.p_and_e_rollup_match import p_and_e_blueprint
from app.bib_2_holdings_541 import blueprint_541
from app.bib_2_holdings_541 import blueprint_auth_541
from dotenv import load_dotenv
from app.gift_fund_bibliography import gift_fund_blueprint
import os
from app.gift_fund_bibliography import gift_fund_blueprint
from app.gift_fund_bibliography import auth_gift_fund_bibliography
from flask_cors import CORS, cross_origin


def create_app():
    load_dotenv()

    app = Flask(__name__)
    CORS(app, resources={r"/p_and_e/*": {"origins": "*"}})
    app.secret_key = os.getenv("SECRET_KEY")
    app.register_blueprint(main_blueprint)
    app.register_blueprint(barnes_and_noble_blueprint, url_prefix="/barnes_and_noble")

    app.register_blueprint(blueprint_541, url_prefix="/bib_2_holdings_541")
    app.register_blueprint(blueprint_auth_541, url_prefex="/auth_541")
    CORS(app, resources={r"/p_and_e/*": {"origins": "*"}})
    app.register_blueprint(p_and_e_blueprint, url_prefix="/p_and_e")
    app.register_blueprint(gift_fund_blueprint, url_prefix="/gift_fund_bibliography")
    app.register_blueprint(gift_fund_blueprint, url_prefix="/auth_gift_fund_bibliography")


    return app
