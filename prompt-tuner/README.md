# Prompt Tuner

A simple web application for managing and evaluating AI workflow prompts with an intuitive interface for version control, testing, and optimization.

## Description

The Prompt Tuner provides a centralized platform for managing prompt templates across your different AI workflows. It offers version management and evaluation capabilities. This application connects to backend APIs to fetch workflows, prompts, schemas and generates forms dynamically based on the workflow requirements.

## Installation & Setup

### Clone and Run Locally

1. **Clone the repository**
   ```bash
   git clone https://github.com/Insight-Services-APAC/ingenious-aux.git

   # Go to prompt-tuner folder
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
   Open your browser and navigate to `http://localhost:5173`

### Docker Container

1. **Build and run with Docker**
   ```bash
   # Build the image
   docker build -t prompt-tuner .
   
   # Run the container
   docker run -p 5173:5173 prompt-tuner
   ```

The application will be available at `http://localhost:5173`

## Documentation

For detailed information and guides, check out our comprehensive documentation in the `docs/` folder:

- **[User Guide](docs/user-guide.md)** - Complete guide on how to use the application
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
