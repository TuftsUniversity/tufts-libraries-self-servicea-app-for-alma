import os
from flask import (
    Blueprint, request, send_file, render_template, current_app
)
from flask_cors import CORS, cross_origin
from io import BytesIO

from .search_swank import SwankSearch

film_search_blueprint = Blueprint("film_search", __name__)
CORS(film_search_blueprint, resources={r"/*": {"origins": "*"}})


# Serve component.js (if you add one later)
@film_search_blueprint.route('/component.js')
@cross_origin()
def serve_component():
    component_path = os.path.join(current_app.root_path, 'film_search')
    return send_file(
        os.path.join(component_path, "component.js"),
        mimetype="application/javascript"
    )


# Component template
@film_search_blueprint.route('/component-template')
@cross_origin()
def serve_component_template():
    return render_template("film-search.html", is_component=True)


# Page (normal)
@film_search_blueprint.route('/', methods=["GET"])
@cross_origin()
def index():
    return render_template("film-search.html", is_component=False)


# Search endpoint
@film_search_blueprint.route('/search', methods=["POST", "OPTIONS"])
@cross_origin(origins="*", headers=["Content-Type", "Authorization"])
def run_search():
    film_title = request.form.get("film_title", "").strip()

    if not film_title:
        return {"error": "Film title is required"}, 400

    processor = SwankSearch(film_title)
    excel_buffer, filename = processor.process()

    return send_file(
        excel_buffer,
        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
        as_attachment=True,
        download_name=filename,
    )
