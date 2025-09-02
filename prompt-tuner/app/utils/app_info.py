"""
Application Information Utilities
Provides dynamic application metadata for health checks and monitoring
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any


def get_app_info() -> Dict[str, Any]:
    """
    Get application information dynamically from project configuration
    
    Returns:
        dict: Application metadata including name, version, python version, etc.
    """
    try:
        # Try to read version from pyproject.toml
        project_root = Path(__file__).parent.parent
        pyproject_path = project_root / "pyproject.toml"
        
        app_name = "prompt-tuner"
        app_version = "unknown"
        
        if pyproject_path.exists():
            with open(pyproject_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('name = '):
                        app_name = line.split('=')[1].strip().strip('"\'')
                    elif line.startswith('version = '):
                        app_version = line.split('=')[1].strip().strip('"\'')
        
        return {
            'name': app_name,
            'version': app_version,
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'environment': os.getenv('FLASK_ENV', 'development'),
            'debug_mode': os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
        }
    except Exception as e:
        # Fallback values if reading fails
        return {
            'name': 'prompt-tuner',
            'version': 'unknown',
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'environment': os.getenv('FLASK_ENV', 'development'),
            'debug_mode': os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
            'error': f"Failed to read project info: {str(e)}"
        }


def get_health_status() -> Dict[str, Any]:
    """
    Generate health status information
    
    Returns:
        dict: Health check response with application info
    """
    from datetime import datetime
    
    app_info = get_app_info()
    
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'service': app_info['name'],
        'version': app_info['version'],
        'python_version': app_info['python_version'],
        'environment': app_info['environment']
    }
