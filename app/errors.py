from flask import render_template
from app import app, db


@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    # avoid having database in bad state
    db.session.rollback()
    return render_template("500.html"), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template("403.html"), 403

@app.errorhandler(400)
def bad_request_error(error):
    return render_template("400.html"), 400

@app.errorhandler(503)
def service_unavailable_error(error):
    return render_template("503.html"), 503

@app.errorhandler(405)
def method_not_allowed(error):
    return render_template("405.html"), 405

@app.errorhandler(413)
def too_large(errot):
    return render_template("413.html"), 413