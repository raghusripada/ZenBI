.PHONY: all setup-db run-backend run-frontend install-backend install-frontend

all: install-backend install-frontend run-backend run-frontend

# Installs backend dependencies using Poetry
install-backend:
	@echo "Installing backend dependencies..."
	@poetry install

# Installs frontend dependencies using npm
install-frontend:
	@echo "Installing frontend dependencies..."
	@cd frontend && npm install

# Sets up the sample database by calling the FastAPI endpoint
setup-db:
	@echo "Setting up sample database..."
	@curl -X GET http://127.0.0.1:8000/api/admin/setup-sample-db || echo "Failed to setup database. Is the backend running?"
	@echo "" # Newline for better readability

# Runs the FastAPI backend server using Uvicorn (through Poetry)
run-backend:
	@echo "Starting backend server on http://127.0.0.1:8000..."
	@poetry run uvicorn zenbi.api.main:app --reload --port 8000

# Runs the React frontend development server (through npm in frontend dir)
run-frontend:
	@echo "Starting frontend development server on http://localhost:5173 (or similar)..."
	@cd frontend && npm run dev

# Target to run everything (useful for a combined dev setup, though often run in separate terminals)
# This will run backend then frontend. Frontend will block the terminal.
# Consider running them in background or separate terminals for simultaneous dev.
run-all-dev: install-backend install-frontend setup-db run-backend-bg run-frontend
	@echo "Backend and frontend started."

# Helper to run backend in background (simple version, might need more robust process management)
run-backend-bg:
	@echo "Starting backend server in background..."
	@poetry run uvicorn zenbi.api.main:app --reload --port 8000 &
	@sleep 2 # Give backend a moment to start before other commands might rely on it (like setup-db)

clean:
	@echo "Cleaning up..."
	@rm -f zenbi_data.db # Remove SQLite DB file
	@# Add other clean commands if needed, e.g., for __pycache__ or frontend build artifacts
	@echo "Cleanup complete."

help:
	@echo "Available commands:"
	@echo "  make install-backend   - Install backend dependencies"
	@echo "  make install-frontend  - Install frontend dependencies"
	@echo "  make setup-db          - Setup/reset the sample SQLite database (backend must be running)"
	@echo "  make run-backend       - Start the FastAPI backend server"
	@echo "  make run-frontend      - Start the React frontend dev server"
	@echo "  make run-all-dev       - Install, setup DB, and run both backend (backgrounded) and frontend"
	@echo "  make clean             - Remove database file and other temporary files"
	@echo "  make help              - Show this help message"

# Default to help if no target is specified
.DEFAULT_GOAL := help
