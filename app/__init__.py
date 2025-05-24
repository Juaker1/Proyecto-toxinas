from flask import Flask
from app.routes.viewer_routes import viewer_bp  

def create_app():
    app = Flask(__name__)
    app.register_blueprint(viewer_bp)  
    return app
