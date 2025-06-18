#!/bin/bash
set -e
set -o pipefail

echo "Starting ZenBI Installation..."
echo "=============================="
echo ""

# --- Prerequisite Checks ---
echo "Checking prerequisites..."
check_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "WARNING: '$1' not found. Please install it for $2."
    else
        echo "INFO: '$1' found."
    fi
}

check_command "python3" "running the backend"
check_command "pip3" "installing Python dependencies (if not using Poetry directly)"
check_command "poetry" "managing backend Python dependencies"
check_command "node" "running the frontend and its build process"
if command -v "yarn" >/dev/null 2>&1; then
    check_command "yarn" "managing frontend dependencies"
    FRONTEND_PKG_MANAGER="yarn"
elif command -v "npm" >/dev/null 2>&1; then
    check_command "npm" "managing frontend dependencies"
    FRONTEND_PKG_MANAGER="npm"
else
    echo "WARNING: Neither 'yarn' nor 'npm' found. Frontend dependencies may need manual installation."
    FRONTEND_PKG_MANAGER=""
fi
echo "Prerequisite check complete."
echo ""

# --- Backend Dependency Installation ---
echo "Installing backend dependencies..."
if [[ -f "Makefile" ]] && grep -q "install-backend:" "Makefile"; then
    if make install-backend; then
        echo "INFO: Backend dependencies installed successfully via 'make install-backend'."
    else
        echo "ERROR: 'make install-backend' failed. Please check Makefile and Poetry setup." >&2
        exit 1
    fi
elif command -v "poetry" >/dev/null 2>&1 && [[ -f "pyproject.toml" ]]; then
    if poetry install --no-root; then # --no-root is often preferred for applications
        echo "INFO: Backend dependencies installed successfully via 'poetry install'."
    else
        echo "ERROR: 'poetry install' failed. Please check your Poetry setup and pyproject.toml." >&2
        exit 1
    fi
else
    echo "ERROR: Could not find Makefile with 'install-backend' target or a Poetry project. Please install backend dependencies manually." >&2
    exit 1
fi
echo "Backend dependency installation complete."
echo ""

# --- Frontend Dependency Installation ---
echo "Installing frontend dependencies..."
if [[ -d "frontend" ]] && [[ -f "frontend/package.json" ]]; then
    cd frontend
    if [[ "$FRONTEND_PKG_MANAGER" == "yarn" ]]; then
        if yarn install; then
            echo "INFO: Frontend dependencies installed successfully via 'yarn install'."
        else
            echo "ERROR: 'yarn install' failed. Please check your Yarn setup and frontend/package.json." >&2
            cd ..
            exit 1
        fi
    elif [[ "$FRONTEND_PKG_MANAGER" == "npm" ]]; then
        if npm install; then
            echo "INFO: Frontend dependencies installed successfully via 'npm install'."
        else
            echo "ERROR: 'npm install' failed. Please check your NPM setup and frontend/package.json." >&2
            cd ..
            exit 1
        fi
    else
        echo "WARNING: No supported frontend package manager (yarn/npm) found, or lock file missing. Skipping frontend dependency installation. Please install manually if needed."
    fi
    cd ..
else
    echo "INFO: 'frontend/package.json' not found or 'frontend' directory missing. Skipping frontend dependency installation."
fi
echo "Frontend dependency installation complete."
echo ""

# --- Environment File Setup ---
echo "Setting up environment file..."
if [[ -f ".env" ]]; then
    echo "INFO: .env file already exists. Please ensure it is configured correctly."
else
    if [[ -f ".env.template" ]]; then
        cp .env.template .env
        echo "INFO: .env.template has been copied to .env."
        echo "IMPORTANT: Please edit the .env file now to set your API keys (e.g., OPENAI_API_KEY),"
        echo "           LLM_PROVIDER, Ollama settings (if using Ollama), OpenMetadata settings (if using),"
        echo "           and any other necessary configurations."
    else
        echo "WARNING: .env.template not found. A .env file could not be created automatically."
        echo "           Please create a .env file manually with necessary configurations based on the README."
    fi
fi
echo ""

# --- Final Instructions ---
echo "---------------------------------------------------------------------"
echo "ZenBI Core Installation Steps Complete!"
echo "---------------------------------------------------------------------"
echo ""
echo "IMPORTANT NEXT STEPS:"
echo ""
echo "1. CONFIGURE YOUR '.env' FILE:"
echo "   Open the '.env' file in the project root and fill in all required values,"
echo "   especially:"
echo "     - LLM_PROVIDER (e.g., 'openai' or 'ollama')"
echo "     - OPENAI_API_KEY (if using OpenAI)"
echo "     - Ollama settings (OLLAMA_BASE_URL, OLLAMA_MODEL_ZENSQL if using Ollama)"
echo "     - OpenMetadata settings (if you plan to use that feature)"
echo ""
echo "2. SET UP THE SAMPLE DATABASE (Requires backend to be running):"
echo "   a. Start the backend server in one terminal: make run-backend"
echo "      (or: poetry run uvicorn zenbi.api.main:app --reload --port 8000)"
echo "   b. In a *separate* terminal, run: make setup-db"
echo "      (or: curl -X GET http://127.0.0.1:8000/api/admin/setup-sample-db)"
echo "      This creates 'zenbi_data.db' with sample tables and data."
echo "   c. You can then stop the backend server (Ctrl+C) if you are not running the full app yet."
echo ""
echo "3. RUN THE APPLICATION:"
echo "   - To run everything (after .env configuration and DB setup):"
echo "     make run-all-dev"
echo "   - Or run individually:"
echo "     Backend: make run-backend"
echo "     Frontend: make run-frontend (in a new terminal)"
echo ""
echo "4. ACCESS ZENBI:"
echo "   - Backend API will be available at http://127.0.0.1:8000"
echo "   - Frontend will be available at http://localhost:3000 (for create-react-app) or http://localhost:5173 (for Vite)" # Vite is used, so 5173
echo ""
echo "Refer to README.md for more details."
echo "Enjoy using ZenBI!"
