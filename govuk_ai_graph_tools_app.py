from flask import Flask
from flask import Blueprint
import os

root = Blueprint('/', __name__, url_prefix='/')
healthcheck = Blueprint('healthcheck', __name__, url_prefix='/healthcheck')


@root.route("/")
def db_test():
    return "<p>Hello, World!</p>"

@healthcheck.route("/ready")
def ready():
    return "<p>Application OK"

def create_app():
    app = Flask(__name__)
    app.register_blueprint(root)
    app.register_blueprint(healthcheck)
    return app

if __name__ == '__main__':
    create_app().run(host='0.0.0.0', port=3000)