from flask import Blueprint, request, render_template, send_file
from app.gift_fund_bibliography.gift_fund_bibliography import GiftFundBibliography
from app.gift_fund_bibliography.auth_gift_fund_bibliography import login_required

gift_fund_blueprint = Blueprint(
    "gift_fund_bibliography", __name__, url_prefix="/gift_fund_bibliography"
)


@gift_fund_blueprint.route("/", methods=["GET"])
@login_required
def index():
    return render_template("gift_fund_bibliography.html")


@gift_fund_blueprint.route("/process", methods=["POST"])
@login_required
def process():
    library = request.form.get("library")
    fiscal_year = request.form.get("fiscal_year")
    if not library or not fiscal_year:
        return "Library and Fiscal Year are required", 400

    gift_fund_bibliography = GiftFundBibliography(library, fiscal_year)
    zip_file = gift_fund_bibliography.process()

    return send_file(
        zip_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name="gift_fund_bibliography.zip",
    )
