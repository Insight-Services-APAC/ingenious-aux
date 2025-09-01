# Prompt Tuner

A web application for managing and evaluating AI workflow prompts with an intuitive interface for version control, testing, and optimization.

## Description

Prompt Tuner provides a centralized platform for managing prompt templates across your different AI workflows. Built with Flask and Alpine.js, it offers dynamic form generation, version management, and evaluation capabilities. The application connects to backend APIs to fetch workflows, schemas and generates forms dynamically based on the workflow requirements.

> **Learn how to use the application** - Check out the [User Guide](docs/user-guide.md)

## Installation & Setup

### Clone and Run Locally

1. **Clone the repository**
   ```bash
   git clone https://github.com/Insight-Services-APAC/ingenious-aux.git
   cd ingenious-aux/prompt-tuner
   ```

2. **Install dependencies**
   ```bash
   # Install uv (if not already installed)
   pip install uv
   
   # Install project dependencies
   uv sync
   ```

3. **Run the application**
   ```bash
   python -m app.app
   ```

4. **Access the application**
   Open your browser and navigate to `http://localhost:5000`

### Docker Container

1. **Build and run with Docker**
   ```bash
   # Build the image
   docker build -t prompt-tuner .
   
   # Run the container
   docker run -p 5000:5000 prompt-tuner
   ```

The application will be available at `http://localhost:5000`

## Technologies & Libraries

- **[Flask 3.1.2+](https://flask.palletsprojects.com/)** - Python web framework with modern async support
- **[Alpine.js 3.13.3](https://alpinejs.dev/)** - Minimal reactive framework (only 15kb gzipped)
- **[Bootstrap 5.3.2](https://getbootstrap.com/)** - CSS framework for responsive design and components
- **[Bootstrap Icons 1.11.1](https://icons.getbootstrap.com/)** - SVG icon library with 1,800+ icons
- **[Flask-CORS 6.0.1](https://flask-cors.readthedocs.io/)** - Cross-Origin Resource Sharing support for API access
- **[uv](https://github.com/astral-sh/uv)** - Ultra-fast Python package installer and resolver

## Project Structure

```
prompt-tuner/
├── app/
│   ├── static/
│   │   ├── css/           # Modular CSS files for each page
│   │   ├── js/            # Alpine.js components and API logic
│   │   └── images/        # Application assets and icons
│   └── templates/         # Jinja2 HTML templates
├── config/                # Configuration files
├── docs/                  # Documentation
├── scripts/               # Build and deployment scripts
├── tests/                 # Test suite
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

**Notable Directories:**
- [`app/static/js/`](app/static/js/) - Contains JavaScript modules for page-specific functionality and API configuration
- [`app/static/css/`](app/static/css/) - Page-specific stylesheets with modern CSS features like backdrop filters and CSS Grid
- [`app/templates/`](app/templates/) - Jinja2 templates with Alpine.js directives for reactive behavior

## Architecture Highlights

The application uses a **component-based architecture** where each page ([`index.html`](app/templates/index.html) - workflow hub, [`manage-prompt.html`](app/templates/manage-prompt.html), [`evaluation.html`](app/templates/evaluation.html), [`workflow-process.html`](app/templates/workflow-process.html)) has dedicated CSS and JavaScript files for modular functionality.

**API Integration:** The app communicates with external workflow APIs through a centralized configuration system in [`api.js`](app/static/js/api.js), enabling easy endpoint management and environment switching.

**Containerization:** Docker setup with multi-stage builds using Python 3.12 slim base image, optimized for production deployment with health checks and non-root user security.
