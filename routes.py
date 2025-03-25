from flask import Blueprint

routes = Blueprint('routes', __name__)

@routes.route('/hello', methods=['GET'])
def hello():
    return "Hello, World!"