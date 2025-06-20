# ZenBI - Natural Language to SQL and BI Platform

ZenBI is a business intelligence platform that allows users to query databases using natural language, generate SQL, and visualize results. It features a semantic layer for defining data models and can integrate with OpenMetadata for metadata discovery. ZenBI supports multiple LLM providers, including OpenAI and local Ollama instances.

## Features

*   **Natural Language Querying:** Ask questions in plain English to get insights from your data.
*   **ZenSQL Generation:** Translates natural language queries into an intermediate semantic SQL (ZenSQL).
*   **SQL Transpilation:** Converts ZenSQL into the target database dialect (e.g., SQLite, PostgreSQL).
*   **Database Interaction:** Executes generated SQL queries against your database.
*   **Chart Suggestions & Visualization:** Provides chart suggestions based on query results and renders them.
*   **Semantic Layer:** Define your data models (tables, columns, relationships, calculated fields) in YAML for a business-friendly view of your data.
*   **OpenMetadata Integration (Optional):** Discover and import table metadata from OpenMetadata to bootstrap your semantic models.
*   **Flexible LLM Configuration:** Supports both OpenAI (cloud-based) and Ollama (local) LLM providers.

## Quick Installation (Recommended)

For a streamlined setup, you can use the provided installation script. This script will check for prerequisites, install backend and frontend dependencies, and help set up the environment file.

1.  **Ensure Prerequisites:** Before running the script, make sure you have essential tools like Python 3.9+, Poetry, Node.js, and npm/yarn. The script will check for these and warn if they are missing.
2.  **Run the Installer:**
    ```bash
    chmod +x install.sh
    ./install.sh
    ```
    The script will guide you through the installation process. It performs the following main actions:
    *   Checks for necessary prerequisite commands (python, poetry, node, npm/yarn).
    *   Installs backend Python dependencies using `make install-backend` (which typically calls `poetry install`).
    *   Installs frontend Node.js dependencies by running `npm install` or `yarn install` in the `frontend` directory.
    *   Copies `.env.template` to `.env` if `.env` doesn't already exist.

3.  **IMPORTANT: Configure `.env` File:**
    After running `install.sh`, you **must** manually edit the `.env` file created in the project root. This file contains placeholders for essential configurations. Update it with your actual settings, particularly:
    *   `LLM_PROVIDER` (choose "openai" or "ollama")
    *   `OPENAI_API_KEY` (if using OpenAI)
    *   Ollama settings (`OLLAMA_BASE_URL`, `OLLAMA_MODEL_ZENSQL`) if using Ollama.
    *   OpenMetadata connection details if you plan to use that feature.
    The application will not function correctly without these settings. Refer to the **Configuration** section below for details on all variables.

Once these steps are complete, proceed to the **Initialize Sample Database** and **Running the Application** sections.

## Manual Installation and Setup

If you prefer a manual setup or need to troubleshoot, follow these detailed steps:

### Prerequisites

*   Python 3.9+
*   Poetry (for Python package management)
*   Node.js and npm/yarn (for the frontend)
*   An OpenAI API key (if using OpenAI as the LLM provider)
*   Ollama installed and running (if using Ollama as the LLM provider)
*   OpenMetadata instance (optional, for metadata import features)

### 1. Clone the Repository

```bash
git clone <repository_url> # Replace <repository_url> with the actual URL
cd zenbi
```

### 2. Setup Backend

*   **Install Dependencies:**
    ```bash
    poetry install
    ```
    (This is typically handled by `make install-backend` as well).

*   **Configure Environment Variables:**
    Copy the environment variable template if it wasn't done by a script:
    ```bash
    cp .env.template .env
    ```
    Edit the `.env` file to configure ZenBI. See the **Configuration** section below for details.

### 3. Setup Frontend

*   **Navigate to Frontend Directory and Install Dependencies:**
    ```bash
    cd frontend
    npm install # or yarn install if you prefer and have it installed
    cd ..
    ```
    (This is typically handled by `make install-frontend`).

### 4. Initialize Sample Database

(This section remains the same - it's a post-installation step)
The application uses a SQLite database (`zenbi_data.db`) by default, which will be created in the project root. To set up the schema and populate it with sample data, run the following command **after the backend server is running**:

*   **Using Makefile (Recommended):**
    ```bash
    make setup-db
    ```
    (This command might require the backend to be running in another terminal: `make run-backend`)

*   **Alternatively, using `curl` (after backend is running):**
    ```bash
    curl -X GET http://127.0.0.1:8000/api/admin/setup-sample-db
    ```

## Configuration

(This section remains largely the same but is now referenced by both installation methods)
ZenBI is configured through environment variables defined in the `.env` file.

### LLM Configuration
... (rest of the Configuration section remains the same as before) ...

#### OpenAI Configuration
...

#### Ollama Configuration
...

**Using Ollama:**
...

### OpenMetadata Configuration (Optional)
...

## Running the Application
... (This section remains the same) ...

## Key API Endpoints
... (This section remains the same) ...

## Testing
... (This section remains the same) ...

## Project Structure
... (This section remains the same) ...

## Roadmap / Future Development

For a detailed list of planned enhancements and future development ideas for ZenBI, please see the [ROADMAP.md](ROADMAP.md) file.

## Contributing
... (This section remains the same) ...
```
