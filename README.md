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

## Getting Started

### Prerequisites

*   Python 3.9+
*   Poetry (for Python package management)
*   Node.js and npm (for the frontend)
*   An OpenAI API key (if using OpenAI as the LLM provider)
*   Ollama installed and running (if using Ollama as the LLM provider)
*   OpenMetadata instance (optional, for metadata import features)

### 1. Clone the Repository

```bash
git clone <repository_url>
cd zenbi
```

### 2. Setup Backend

*   **Install Dependencies:**
    ```bash
    poetry install
    ```

*   **Configure Environment Variables:**
    Copy the environment variable template:
    ```bash
    cp .env.template .env
    ```
    Now, edit the `.env` file to configure ZenBI according to your setup. See the **Configuration** section below for details on each variable.

### 3. Setup Frontend

*   **Navigate to Frontend Directory and Install Dependencies:**
    ```bash
    cd frontend
    npm install
    cd ..
    ```

### 4. Initialize Sample Database

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

ZenBI is configured through environment variables defined in the `.env` file.

### LLM Configuration

You can choose between OpenAI and Ollama as your LLM provider.

*   `LLM_PROVIDER`: Specifies the LLM provider.
    *   Options: `"openai"`, `"ollama"`
    *   Default: `"openai"` (if not set, the application defaults to OpenAI, but requires `OPENAI_API_KEY`)
    *   Example: `LLM_PROVIDER="ollama"`

#### OpenAI Configuration

Required if `LLM_PROVIDER="openai"`.

*   `OPENAI_API_KEY`: Your API key from OpenAI.
    *   Example: `OPENAI_API_KEY="sk-your_openai_api_key_here"`
*   `OPENAI_MODEL_NAME`: (Optional) The OpenAI model to use.
    *   Default: `"gpt-3.5-turbo"`
    *   Example: `OPENAI_MODEL_NAME="gpt-4"`

#### Ollama Configuration

Required if `LLM_PROVIDER="ollama"`.

*   `OLLAMA_BASE_URL`: The base URL for your running Ollama instance.
    *   Default: `"http://localhost:11434"`
    *   Example: `OLLAMA_BASE_URL="http://127.0.0.1:11434"`
*   `OLLAMA_MODEL_ZENSQL`: The Ollama model to use for generating ZenSQL and chart suggestions.
    *   Default: `"llama3.1:8b"`
    *   Example: `OLLAMA_MODEL_ZENSQL="mistral:latest"`
*   `OLLAMA_MODEL_CHART`: (Optional) The Ollama model specifically for chart suggestions. If not set, `OLLAMA_MODEL_ZENSQL` is used.
    *   Default: Value of `OLLAMA_MODEL_ZENSQL` (or "llama3.1:8b" if `OLLAMA_MODEL_ZENSQL` is also not set)
    *   Example: `OLLAMA_MODEL_CHART="mistral:latest"`

**Using Ollama:**

1.  **Install Ollama:** Follow the instructions on the [Ollama official website](https://ollama.ai/).
2.  **Download Models:** Pull the models you intend to use. For the default configuration:
    ```bash
    ollama pull llama3.1:8b
    ```
    If you configure other models (e.g., `mistral:latest`), pull them accordingly.
3.  **Ensure Ollama is Running:** The Ollama service must be running for ZenBI to connect to it.
4.  **Prompt Engineering:** The default prompts in `zenbi/core/llm_service.py` are optimized for general-purpose models like GPT-3.5/4 and Llama 3.1. If you use different Ollama models, especially smaller or specialized ones, you might need to experiment with and adjust these prompt templates for optimal performance.

### OpenMetadata Configuration (Optional)

Configure these if you want to use the OpenMetadata import feature (`/api/admin/import-from-openmetadata`).

*   `OM_SERVER_URL`: URL of your OpenMetadata server's API.
    *   Example: `OM_SERVER_URL="http://localhost:8585/api"`
*   `OM_AUTH_PROVIDER`: Authentication provider for OpenMetadata.
    *   Options: `"no-auth"`, `"openmetadata"`, `"google"`
    *   Default: `"no-auth"`
*   `OM_JWT_TOKEN`: JWT token if `OM_AUTH_PROVIDER="openmetadata"`.
*   `OM_SECRET_KEY`: Path to Google client secret JSON or the key itself if `OM_AUTH_PROVIDER="google"`.
*   `OM_GOOGLE_CREDENTIALS_PATH`: Path to Google credentials JSON or audience URL (for "google" auth, specific usage may depend on OpenMetadata SDK version).

## Running the Application

It's recommended to run the backend and frontend in separate terminals.

1.  **Run the Backend Server:**
    ```bash
    make run-backend
    ```
    Or directly:
    ```bash
    poetry run uvicorn zenbi.api.main:app --reload --port 8000
    ```
    The API will be available at `http://127.0.0.1:8000`.

2.  **Run the Frontend Application:**
    ```bash
    make run-frontend
    ```
    Or directly:
    ```bash
    cd frontend
    npm run dev
    ```
    The frontend will typically be available at `http://localhost:5173` (Vite) or `http://localhost:3000` (CRA).

3.  **Access ZenBI:** Open your browser and navigate to the frontend URL.

## Key API Endpoints

*   `GET /api/`: Welcome message.
*   `POST /api/query/execute-natural-language`: Main endpoint for processing natural language queries.
    *   Input: `{ "natural_language_query": "your query" }`
    *   (Optional query param: `mdl_file_name=your_mdl.yaml` to use a specific MDL file from `zenbi/data/`)
*   `POST /api/query/generate-zensql`: Generates ZenSQL and chart suggestion from a natural language query.
*   `POST /api/query/transpile-zensql`: Converts ZenSQL to SQL for a target dialect.
*   `GET /api/mdl/load-sample`: Loads and returns the content of an MDL file (default: `sample_mdl.yaml`).
*   `GET /api/admin/setup-sample-db`: Initializes/resets the sample SQLite database.
*   `POST /api/admin/import-from-openmetadata`: Imports table metadata from OpenMetadata to generate an MDL YAML file.
    *   Input: `{ "service_name": "...", "database_name": "...", "schema_name": "..." }`

## Testing

To run the unit tests:

```bash
poetry run python -m unittest discover tests
```
Or, to run a specific test file:
```bash
poetry run python -m unittest tests.core.test_semantic_engine
```

## Project Structure

*   `zenbi/`: Main Python package.
    *   `api/`: FastAPI application, endpoints.
    *   `core/`: Core logic (LLM service, semantic engine, database service, OpenMetadata service, config).
    *   `mdl/`: Pydantic models for the semantic layer, MDL loading/generation logic.
    *   `data/`: Sample MDL YAML files, generated MDL files.
*   `frontend/`: React frontend application.
*   `tests/`: Unit tests.
*   `.env.template`: Template for environment variables.
*   `Makefile`: Convenience script for common tasks.
*   `pyproject.toml`: Python project dependencies and metadata.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
```
