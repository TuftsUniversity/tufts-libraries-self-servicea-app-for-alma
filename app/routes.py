from flask import request, render_template, Blueprint, g
import redis
import json
import os
import app.p_and_e_rollup_match.p_and_e_rollup_match
import app.barnes_and_noble.barnes_and_noble


main = Blueprint("main", __name__)


@main.route("/resource_match", methods=["GET", "POST"])
def resource_match():
    return render_template("resource_match.html")
