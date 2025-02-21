from flask import request, render_template, Blueprint, g
import redis
import json
import os
import app.resource_match


main = Blueprint("main", __name__)


@main.route('/resource_match', methods=['GET', 'POST'])

def resource_match():

    return render_template('resource_match.html')