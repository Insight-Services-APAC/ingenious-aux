"""
Flask Application Entry Point
"""

import os
from flask import Flask, render_template


def create_app():
    """Simple app factory"""
    app = Flask(__name__)
    
    # Minimal required config
    app.config['DEBUG'] = True
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8001)
