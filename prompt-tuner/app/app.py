"""
Flask Application Entry Point
"""

import os
from flask import Flask, render_template, jsonify
from .utils import get_health_status


def create_app():
    """Simple app factory"""
    app = Flask(__name__)
    
    # Minimal required config
    app.config['DEBUG'] = True
    
    @app.route('/health')
    def health_check():
        """Health check endpoint for Docker and monitoring"""
        return jsonify(get_health_status()), 200
    
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/workflow-process')
    def workflow_process():
        return render_template('workflow-process.html')
    
    @app.route('/manage-prompt')
    def manage_prompt():
        return render_template('manage-prompt.html')

    @app.route('/evaluate')
    def prompt_evaluation():
        return render_template('evaluation.html')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5173)