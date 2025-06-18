from fastapi import FastAPI, HTTPException, Body, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import json
import yaml
import re

from zenbi.mdl.loader import load_semantic_layer_from_data_dir, generate_mdl_from_openmetadata
from zenbi.mdl.models import SemanticLayer, ColumnDefinition, CalculatedColumnDefinition
from zenbi.core.config import settings, Settings
from zenbi.core.llm_service import LLMQueryService, serialize_mdl_for_llm
from zenbi.core.semantic_engine import SemanticEngine
from zenbi.core.database_service import DatabaseService
from zenbi.core.openmetadata_service import OpenMetadataService
from sqlalchemy.exc import SQLAlchemyError # For specific DB errors
from pathlib import Path


# --- Pydantic Models for API requests/responses ---
class ZenSQLQueryRequest(BaseModel):
    natural_language_query: str

class ZenSQLQueryResponse(BaseModel):
    natural_language_query: str
    zensql_query: Optional[str] = None
    final_sql_query: Optional[str] = None
    mdl_context_used: Optional[str] = None
    query_results: Optional[List[Dict]] = None
    chart_suggestion: Optional[Dict] = None
    error_message: Optional[str] = None

class TranspileRequest(BaseModel):
    zensql_query: str
    target_dialect: Optional[str] = "sqlite"

class TranspileResponse(BaseModel):
    final_sql: str
    zensql_query: str
    target_dialect: str
    error_message: Optional[str] = None

class SetupDbResponse(BaseModel):
    message: str
    tables_created: Optional[List[str]] = None
    errors: Optional[List[str]] = None # Simplified from tables_dropped

class OpenMetadataImportRequest(BaseModel):
    service_name: str = Field(..., description="Name of the service connector in OpenMetadata")
    database_name: str = Field(..., description="Name of the database in OpenMetadata")
    schema_name: str = Field(..., description="Name of the schema in OpenMetadata")

class OpenMetadataImportResponse(BaseModel):
    message: str
    file_path: Optional[str] = None
    mdl_content_summary: Optional[Dict] = None
    error: Optional[str] = None


# --- FastAPI App Initialization ---
app = FastAPI(
    title="ZenBI API",
    version="0.1.0",
    description="API for ZenBI" # Simplified
)

# --- Global Services ---
def get_app_settings() -> Settings:
    return settings

llm_query_service: Optional[LLMQueryService] = None
if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key_here":
    try:
        llm_query_service = LLMQueryService(settings=settings)
    except ValueError as e: # Catch init errors from LLMQueryService
        print(f"ERROR initializing LLMQueryService: {e}") # Log error
        llm_query_service = None # Ensure it's None if init fails
else:
    print("WARNING: LLMQueryService not initialized (OPENAI_API_KEY not set or is placeholder). Some features may be unavailable.")

db_service = DatabaseService()

_semantic_layer_cache: Optional[SemanticLayer] = None

def get_semantic_layer(force_reload: bool = False, file_name: str = "sample_mdl.yaml") -> SemanticLayer:
    global _semantic_layer_cache
    if force_reload or (_semantic_layer_cache and file_name != getattr(_semantic_layer_cache, "_source_file", "sample_mdl.yaml")):
        _semantic_layer_cache = None
    if _semantic_layer_cache is None:
        try:
            _semantic_layer_cache = load_semantic_layer_from_data_dir(file_name)
            setattr(_semantic_layer_cache, "_source_file", file_name)
            # Minimal additions for sample_mdl.yaml if needed for demos
            if file_name == "sample_mdl.yaml":
                orders_model = next((m for m in _semantic_layer_cache.models if m.name == "orders"), None)
                if orders_model and not any(c.name == "vat_amount" for c in orders_model.columns):
                    orders_model.columns.append(CalculatedColumnDefinition(
                        name="vat_amount", actual_name="vat_calculated", dtype="FLOAT",
                        expression="total_price * 0.20", description="VAT @ 20%"
                    ))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) # Pass FileNotFoundError message
        except Exception as e: # Catch other loading errors
            print(f"Critical error loading semantic model '{file_name}': {e}") # Log critical error
            raise HTTPException(status_code=500, detail=f"Error loading semantic model '{file_name}'.")
    return _semantic_layer_cache

def parse_llm_output_for_chart_and_sql(raw_output: str) -> (Optional[Dict], str):
    chart_suggestion = None; sql_query = raw_output.strip()
    match = re.search(r"/\* ZENBI_CHART_SUGGESTION_START\s*(\{.*?\})\s*ZENBI_CHART_SUGGESTION_END \*/", raw_output, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
        try: chart_suggestion = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Chart JSON parsing error: {e}. JSON: {json_str}"); chart_suggestion = {"error": "Failed to parse chart JSON"}
        sql_query = raw_output[match.end():].strip()
    return chart_suggestion, sql_query

# --- API Endpoints ---
@app.get("/", tags=["General"])
async def root(): return {"message": "Welcome to ZenBI"}

@app.post("/admin/import-from-openmetadata", response_model=OpenMetadataImportResponse, tags=["Admin", "OpenMetadata"])
async def import_from_openmetadata_endpoint(request: OpenMetadataImportRequest, app_settings: Settings = Depends(get_app_settings)):
    if not app_settings.OM_SERVER_URL:
        return OpenMetadataImportResponse(message="OpenMetadata integration not configured.", error="OM_SERVER_URL is not set.")
    om_service: Optional[OpenMetadataService] = None
    try:
        om_service = OpenMetadataService(settings=app_settings)
    except ValueError as e: # Config errors from OpenMetadataService __init__
        return OpenMetadataImportResponse(message="Failed to initialize OpenMetadata service due to configuration.", error=str(e))
    except Exception as e: # Other init errors (e.g., connection)
        print(f"OpenMetadata connection error: {e}") # Log the actual error
        return OpenMetadataImportResponse(message="Failed to connect to OpenMetadata.", error=f"Connection error. Check server logs.")

    try:
        semantic_layer = generate_mdl_from_openmetadata(om_service, request.database_name, request.schema_name, request.service_name)
        if not semantic_layer.models:
            return OpenMetadataImportResponse(message="No models discovered.", mdl_content_summary={"models_count": 0})

        data_dir = Path.cwd() / "zenbi" / "data"; data_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"generated_mdl_{request.service_name}_{request.database_name}_{request.schema_name}.yaml"
        file_path = data_dir / file_name
        mdl_dict = json.loads(semantic_layer.model_dump_json(indent=2))
        with open(file_path, 'w') as f: yaml.dump(mdl_dict, f, sort_keys=False, allow_unicode=True)

        return OpenMetadataImportResponse(message="Import successful.", file_path=str(file_path.relative_to(Path.cwd())), mdl_content_summary={"models_count": len(semantic_layer.models)})
    except Exception as e:
        print(f"Error during OpenMetadata import process: {e}")
        return OpenMetadataImportResponse(message="Error during import from OpenMetadata.", error=str(e))

@app.get("/admin/setup-sample-db", response_model=SetupDbResponse, tags=["Admin"])
async def setup_sample_db_endpoint():
    try:
        semantic_layer = get_semantic_layer(force_reload=True, file_name="sample_mdl.yaml")
        db_service.setup_sample_data(semantic_layer)
        tables_created = [model.actual_table for model in semantic_layer.models if db_service.table_exists(model.actual_table)]
        return SetupDbResponse(message="Sample database setup complete.", tables_created=tables_created)
    except HTTPException: raise # Re-raise HTTPExceptions from get_semantic_layer
    except Exception as e:
        print(f"Error during database setup: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting up database: {str(e)}")

@app.get("/mdl/load-sample", response_model=SemanticLayer, tags=["MDL"])
async def load_sample_mdl_endpoint(file_name: Optional[str] = "sample_mdl.yaml"):
    try: return get_semantic_layer(file_name=file_name)
    except HTTPException: raise # Re-raise from get_semantic_layer

@app.post("/query/generate-zensql", response_model=ZenSQLQueryResponse, tags=["Query"])
async def generate_zensql_endpoint(request_body: ZenSQLQueryRequest = Body(...), mdl_file_name: Optional[str] = "sample_mdl.yaml"):
    mdl_context = ""; zensql_query = ""; chart_suggestion = None
    try:
        if llm_query_service is None: raise HTTPException(status_code=503, detail="LLM Service unavailable.")
        semantic_layer = get_semantic_layer(file_name=mdl_file_name)
        mdl_context = serialize_mdl_for_llm(semantic_layer)
        raw_llm_output = llm_query_service.generate_zensql(semantic_layer, request_body.natural_language_query)
        chart_suggestion, zensql_query = parse_llm_output_for_chart_and_sql(raw_llm_output)
        if not zensql_query and not (chart_suggestion and chart_suggestion.get("error")):
            raise ValueError("LLM did not return a valid SQL query." if not raw_llm_output.strip().startswith("-- Error") else raw_llm_output)
        return ZenSQLQueryResponse(natural_language_query=request_body.natural_language_query, zensql_query=zensql_query, mdl_context_used=mdl_context, chart_suggestion=chart_suggestion)
    except HTTPException: raise
    except Exception as e:
        return ZenSQLQueryResponse(natural_language_query=request_body.natural_language_query, mdl_context_used=mdl_context, chart_suggestion=chart_suggestion, zensql_query=zensql_query, error_message=str(e))

@app.post("/query/transpile-zensql", response_model=TranspileResponse, tags=["Query"])
async def transpile_zensql_endpoint(request_body: TranspileRequest = Body(...), mdl_file_name: Optional[str] = "sample_mdl.yaml"):
    try:
        semantic_layer = get_semantic_layer(file_name=mdl_file_name)
        engine = SemanticEngine(semantic_layer, target_dialect=request_body.target_dialect or "sqlite")
        final_sql = engine.transpile_zensql_to_sql(request_body.zensql_query)
        return TranspileResponse(final_sql=final_sql, zensql_query=request_body.zensql_query, target_dialect=engine.target_dialect)
    except HTTPException: raise
    except ValueError as e: # SemanticEngine specific errors (parsing, transformation)
         return TranspileResponse(final_sql="", zensql_query=request_body.zensql_query, target_dialect=request_body.target_dialect or "sqlite", error_message=str(e))
    except Exception as e:
        print(f"Unexpected transpilation error: {e}")
        return TranspileResponse(final_sql="", zensql_query=request_body.zensql_query, target_dialect=request_body.target_dialect or "sqlite", error_message="Unexpected error during SQL transpilation.")

@app.post("/query/execute-natural-language", response_model=ZenSQLQueryResponse, tags=["Query"])
async def execute_natural_language_query(request: ZenSQLQueryRequest = Body(...), mdl_file_name: Optional[str] = "sample_mdl.yaml"):
    # Initialize all response fields to ensure they are present, even if None
    response_data = ZenSQLQueryResponse(natural_language_query=request.natural_language_query)
    try:
        semantic_layer = get_semantic_layer(file_name=mdl_file_name) # Can raise HTTPException
        response_data.mdl_context_used = serialize_mdl_for_llm(semantic_layer)

        if llm_query_service is None: raise HTTPException(status_code=503, detail="LLM Service unavailable.")

        # 1. Generate ZenSQL and Chart Suggestion
        try:
            raw_llm_output = llm_query_service.generate_zensql(semantic_layer, request.natural_language_query)
            response_data.chart_suggestion, response_data.zensql_query = parse_llm_output_for_chart_and_sql(raw_llm_output)
            if not response_data.zensql_query and not (response_data.chart_suggestion and response_data.chart_suggestion.get("error")):
                err_msg = "LLM did not return a valid SQL query."
                if raw_llm_output and raw_llm_output.strip().startswith("-- Error"): err_msg = raw_llm_output.strip()
                raise ValueError(err_msg) # Specific error for this stage
        except Exception as e:
            response_data.error_message = f"LLM Query Generation Error: {str(e)}"
            return response_data # Return immediately with error

        # 2. Transpile ZenSQL to SQL
        try:
            semantic_engine = SemanticEngine(semantic_layer, target_dialect="sqlite")
            response_data.final_sql_query = semantic_engine.transpile_zensql_to_sql(response_data.zensql_query)
        except Exception as e: # Catch SemanticEngine's ValueError or other errors
            response_data.error_message = f"SQL Transpilation Error: {str(e)}"
            return response_data # Return with error

        # 3. Execute SQL Query
        try:
            response_data.query_results = db_service.execute_query(response_data.final_sql_query)
        except SQLAlchemyError as e:
            response_data.error_message = f"Database Execution Error: {str(e)}"
            # Query results will be None, error message will be set.
        except Exception as e: # Other unexpected errors during execution
            response_data.error_message = f"Unexpected Database Error: {str(e)}"

    except HTTPException as e_http: # Catch HTTPExceptions from get_semantic_layer or LLM check
        response_data.error_message = e_http.detail # Use detail from HTTPException
    except Exception as e_global: # Catch-all for other unexpected errors (like ValueError from step 1)
        response_data.error_message = f"Global Error: {str(e_global)}"

    return response_data
