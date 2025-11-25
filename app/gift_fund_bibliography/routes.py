from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    send_file,
    current_app,
    render_template,
    send_from_directory,
    jsonify,
    session
)
from app.gift_fund_bibliography.gift_fund_bibliography import GiftFundBibliography
from app.gift_fund_bibliography.auth_gift_fund_bibliography import login_required
from app.gift_fund_bibliography.auth_gift_fund_bibliography import verify_token_or_reject
from flask_cors import CORS, cross_origin
gift_fund_blueprint = Blueprint(
    "gift_fund_bibliography", __name__, url_prefix="/gift_fund_bibliography"
)

import os
from flask_cors import CORS, cross_origin
# Serve component.js
@gift_fund_blueprint.route('/component.js')
@cross_origin()
def serve_component():
    component_path = os.path.dirname(__file__)  # points to app/gift_fund_bibliography/
    return send_from_directory(component_path, 'component.js', mimetype='application/javascript')

# Serve component-template
@gift_fund_blueprint.route('/component-template')
@cross_origin()
def serve_component_template():


    return render_template("gift_fund_bibliography.html", is_component=True)



@gift_fund_blueprint.route("/", methods=["GET"])
@login_required
def index():
    return render_template("gift_fund_bibliography.html")


@gift_fund_blueprint.route("/process", methods=["POST"])
def process():
    is_component = request.form.get('isComponent')
    if is_component == 'false':
        if 'user' not in session:
            return redirect(url_for('auth_gift_fund_bibliography.login', _scheme="https", _external=True))

    else:
        
    

        # Verify token first
        is_verified, message_or_userid = verify_token_or_reject()
        if not is_verified:
            return jsonify({"error": message_or_userid}), 401

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
