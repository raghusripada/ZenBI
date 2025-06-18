from fastapi import FastAPI, HTTPException, Body, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import json
import yaml
import re
import logging

from zenbi.mdl.loader import load_semantic_layer_from_data_dir, generate_mdl_from_openmetadata
from zenbi.mdl.models import SemanticLayer, ColumnDefinition, CalculatedColumnDefinition
from zenbi.core.config import settings, Settings
from zenbi.core.llm_service import LLMQueryService, serialize_mdl_for_llm
from zenbi.core.semantic_engine import SemanticEngine
from zenbi.core.database_service import DatabaseService
from zenbi.core.openmetadata_service import OpenMetadataService
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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
    textual_insight: Optional[str] = None # New field for textual insight
    error_message: Optional[str] = None

# ... (other Pydantic models remain the same) ...
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
    errors: Optional[List[str]] = None

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
    description="API for ZenBI"
)

# --- Global Services ---
# ... (get_app_settings, llm_service, db_service, _semantic_layer_cache, get_semantic_layer, parse_llm_output_for_chart_and_sql remain the same) ...
def get_app_settings() -> Settings:
    return settings

llm_service: Optional[LLMQueryService] = None
try:
    llm_service = LLMQueryService(settings=settings)
except ValueError as e:
    logger.error(f"Failed to initialize LLMQueryService during application startup: {e}")
    llm_service = None
except Exception as e:
    logger.error(f"An unexpected error occurred during LLMQueryService initialization: {e}")
    llm_service = None

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
            if file_name == "sample_mdl.yaml":
                orders_model = next((m for m in _semantic_layer_cache.models if m.name == "orders"), None)
                if orders_model and not any(c.name == "vat_amount" for c in orders_model.columns):
                    orders_model.columns.append(CalculatedColumnDefinition(
                        name="vat_amount", actual_name="vat_calculated", dtype="FLOAT",
                        expression="total_price * 0.20", description="VAT @ 20%"
                    ))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Critical error loading semantic model '{file_name}': {e}")
            raise HTTPException(status_code=500, detail=f"Error loading semantic model '{file_name}'.")
    return _semantic_layer_cache

def parse_llm_output_for_chart_and_sql(raw_output: str) -> (Optional[Dict], str):
    chart_suggestion = None; sql_query = raw_output.strip()
    match = re.search(r"/\* ZENBI_CHART_SUGGESTION_START\s*(\{.*?\})\s*ZENBI_CHART_SUGGESTION_END \*/", raw_output, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
        try: chart_suggestion = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Chart JSON parsing error: {e}. JSON: {json_str}"); chart_suggestion = {"error": "Failed to parse chart JSON"}
        sql_query = raw_output[match.end():].strip()
    return chart_suggestion, sql_query
# --- API Endpoints ---
@app.get("/", tags=["General"])
async def root(): return {"message": "Welcome to ZenBI"}

# ... (other admin and utility endpoints remain the same) ...
@app.post("/admin/import-from-openmetadata", response_model=OpenMetadataImportResponse, tags=["Admin", "OpenMetadata"])
async def import_from_openmetadata_endpoint(request: OpenMetadataImportRequest, app_settings: Settings = Depends(get_app_settings)):
    if not app_settings.OM_SERVER_URL:
        raise HTTPException(status_code=400, detail="OpenMetadata integration is not configured (OM_SERVER_URL is not set).")
    om_service: Optional[OpenMetadataService] = None
    try:
        om_service = OpenMetadataService(settings=app_settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Failed to initialize OpenMetadata service: {e}")
    except Exception as e:
        logger.error(f"OpenMetadata connection error: {e}")
        raise HTTPException(status_code=503, detail="Failed to connect to OpenMetadata. Check server logs.")

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
        logger.error(f"Error during OpenMetadata import process: {e}")
        raise HTTPException(status_code=500, detail=f"Error during import from OpenMetadata: {e}")


@app.get("/admin/setup-sample-db", response_model=SetupDbResponse, tags=["Admin"])
async def setup_sample_db_endpoint():
    try:
        semantic_layer = get_semantic_layer(force_reload=True, file_name="sample_mdl.yaml")
        db_service.setup_sample_data(semantic_layer)
        tables_created = [model.actual_table for model in semantic_layer.models if db_service.table_exists(model.actual_table)]
        return SetupDbResponse(message="Sample database setup complete.", tables_created=tables_created)
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error during database setup: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting up database: {str(e)}")

@app.get("/mdl/load-sample", response_model=SemanticLayer, tags=["MDL"])
async def load_sample_mdl_endpoint(file_name: Optional[str] = "sample_mdl.yaml"):
    return get_semantic_layer(file_name=file_name)


@app.post("/query/generate-zensql", response_model=ZenSQLQueryResponse, tags=["Query"])
async def generate_zensql_endpoint(request_body: ZenSQLQueryRequest = Body(...), mdl_file_name: Optional[str] = "sample_mdl.yaml"):
    mdl_context = ""; zensql_query = ""; chart_suggestion = None; error_msg = None
    try:
        if not llm_service: raise HTTPException(status_code=503, detail="LLM Service unavailable.")
        semantic_layer = get_semantic_layer(file_name=mdl_file_name)
        mdl_context = serialize_mdl_for_llm(semantic_layer)
        raw_llm_output = llm_service.generate_zensql(semantic_layer, request_body.natural_language_query)
        chart_suggestion, zensql_query = parse_llm_output_for_chart_and_sql(raw_llm_output)
        if not zensql_query and not (chart_suggestion and chart_suggestion.get("error")):
            error_msg = "LLM did not return a valid SQL query."
            if raw_llm_output and raw_llm_output.strip().startswith("-- Error"): error_msg = raw_llm_output.strip()
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error in generate_zensql_endpoint: {e}")
        error_msg = str(e)

    return ZenSQLQueryResponse(
        natural_language_query=request_body.natural_language_query,
        zensql_query=zensql_query,
        mdl_context_used=mdl_context,
        chart_suggestion=chart_suggestion,
        error_message=error_msg
    )

@app.post("/query/transpile-zensql", response_model=TranspileResponse, tags=["Query"])
async def transpile_zensql_endpoint(request_body: TranspileRequest = Body(...), mdl_file_name: Optional[str] = "sample_mdl.yaml"):
    try:
        semantic_layer = get_semantic_layer(file_name=mdl_file_name)
        engine = SemanticEngine(semantic_layer, target_dialect=request_body.target_dialect or "sqlite")
        final_sql = engine.transpile_zensql_to_sql(request_body.zensql_query)
        return TranspileResponse(final_sql=final_sql, zensql_query=request_body.zensql_query, target_dialect=engine.target_dialect)
    except HTTPException: raise
    except ValueError as e:
         raise HTTPException(status_code=400, detail=f"Error in ZenSQL processing: {e}")
    except Exception as e:
        logger.error(f"Unexpected transpilation error: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error during SQL transpilation.")

@app.post("/query/execute-natural-language", response_model=ZenSQLQueryResponse, tags=["Query"])
async def execute_natural_language_query(request: ZenSQLQueryRequest = Body(...), mdl_file_name: Optional[str] = "sample_mdl.yaml"):
    response_data = ZenSQLQueryResponse(natural_language_query=request.natural_language_query)

    try:
        if not llm_service:
            raise HTTPException(status_code=503, detail="LLM Service is not available due to configuration errors.")

        semantic_layer = get_semantic_layer(file_name=mdl_file_name)
        response_data.mdl_context_used = serialize_mdl_for_llm(semantic_layer)

        # Step 1: Generate ZenSQL and Chart Suggestion
        try:
            raw_llm_output = llm_service.generate_zensql(semantic_layer, request.natural_language_query)
            response_data.chart_suggestion, response_data.zensql_query = parse_llm_output_for_chart_and_sql(raw_llm_output)

            if not response_data.zensql_query and not (response_data.chart_suggestion and response_data.chart_suggestion.get("error")):
                err_msg = "LLM did not return a valid SQL query."
                if raw_llm_output and raw_llm_output.strip().startswith("-- Error"): # Check if LLM itself returned an error string
                    err_msg = raw_llm_output.strip()
                raise ValueError(err_msg) # Raise to be caught by the outer try-except for this stage
        except Exception as e:
            logger.error(f"LLM Query Generation Error: {e}")
            response_data.error_message = f"LLM Query Generation Error: {str(e)}"
            return response_data # Return immediately

        # Step 2: Transpile ZenSQL to SQL
        try:
            semantic_engine = SemanticEngine(semantic_layer, target_dialect="sqlite") # Assuming SQLite for execution
            response_data.final_sql_query = semantic_engine.transpile_zensql_to_sql(response_data.zensql_query)
        except Exception as e:
            logger.error(f"SQL Transpilation Error: {e}")
            response_data.error_message = f"SQL Transpilation Error: {str(e)}"
            return response_data # Return with error

        # Step 3: Execute SQL Query
        try:
            response_data.query_results = db_service.execute_query(response_data.final_sql_query)
        except SQLAlchemyError as e:
            logger.error(f"Database Execution Error: {e}")
            response_data.error_message = f"Database Execution Error: {str(e)}"
            # Results will be None, error_message is set. Proceed to insight generation if desired, or return.
            # For now, let's allow insight generation attempt even if DB fails, it might summarize the problem.
        except Exception as e:
            logger.error(f"Unexpected Database Error: {e}")
            response_data.error_message = f"Unexpected Database Error: {str(e)}"

        # Step 4: Generate Textual Insight (only if no prior critical error preventing it)
        # Attempt insight generation even if DB query had an error, as insight might explain the error or lack of data.
        if llm_service and response_data.final_sql_query : # Requires at least the SQL to be generated
            try:
                # Use an empty list for results if query_results is None (e.g., due to DB error)
                # to allow insight generation about the situation.
                results_for_insight = response_data.query_results if response_data.query_results is not None else []

                response_data.textual_insight = llm_service.generate_textual_insight(
                    natural_language_query=request.natural_language_query,
                    final_sql_query=response_data.final_sql_query, # Use the successfully transpiled SQL
                    query_results=results_for_insight
                )
            except Exception as e:
                logger.error(f"Error generating textual insight: {e}")
                # Append to existing error message if any, or set new one
                insight_error = f"Error generating textual insight: {str(e)}"
                if response_data.error_message:
                    response_data.error_message += f"; {insight_error}"
                else:
                    response_data.error_message = insight_error
        else:
            if not response_data.error_message: # If no other error, but insight couldn't be generated
                 response_data.textual_insight = "Textual insight could not be generated due to missing SQL or LLM service unavailability."


    except HTTPException as e_http:
        # This will catch HTTPExceptions from get_semantic_layer or the initial LLM service check
        # Update response_data with this error before returning
        response_data.error_message = e_http.detail
        # We don't re-raise here, instead let the function return the response_data
        # which now includes the error message.
    except Exception as e_global:
        logger.error(f"Global Error in execute_natural_language: {e_global}")
        if response_data.error_message: # Append if an error was already caught from a sub-step
            response_data.error_message += f"; Global error: {str(e_global)}"
        else:
            response_data.error_message = f"An unexpected error occurred: {str(e_global)}"

    return response_data
