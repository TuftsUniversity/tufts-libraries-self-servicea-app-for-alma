from flask import Flask
from .app import main_blueprint
from app.barnes_and_noble.barnes_and_noble import barnes_and_noble_blueprint
from .resources.resource_match import resource_match_blueprint
from app.p_and_e_rollup_match.routes import p_and_e_blueprint


def create_app():
    app = Flask(__name__)
    app.config["UPLOAD_FOLDER"] = "uploads"
    app.config["DOWNLOAD_FOLDER"] = "downloads"

    app.register_blueprint(main_blueprint)
    app.register_blueprint(overlap_analysis_blueprint, url_prefix="/overlap")
    app.register_blueprint(resource_match_blueprint, url_prefix="/resource")
    app.register_blueprint(p_and_e_blueprint, url_prefix="/p_and_e")

    return app
