from flask import Blueprint, render_template, request, send_file, redirect, url_for, flash
from .search_swank import SwankSearch
from .search_criterion import SearchCriterion
film_search_blueprint = Blueprint(
    "film_search", __name__, url_prefix="/film_search"
)


@film_search_blueprint.route("/", methods=["GET"])
def index():
    is_component = request.args.get("is_component", "false").lower() == "true"
    return render_template("film_search.html", is_component=is_component)


@film_search_blueprint.route("/search", methods=["POST"])
def run_search():
    """Run Swank search and return Excel."""
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Please enter a film title.")
        return redirect(url_for("film_search.index"))

    processor = SwankSearch(film_title=title)
    excel_buffer, filename = processor.process()
    excel_buffer.seek(0)

    return send_file(
        excel_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@film_search_blueprint.route("/criterion_search", methods=["POST"])
def run_criterion_search():
    """Run Criterion search and return its own Excel."""
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Please enter a film title.")
        return redirect(url_for("film_search.index"))

    processor = SearchCriterion(film_title=title)
    excel_buffer, filename = processor.process()
    excel_buffer.seek(0)

    return send_file(
        excel_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
