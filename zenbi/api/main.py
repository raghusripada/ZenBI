from fastapi import FastAPI, HTTPException, Body, Depends
from pydantic import BaseModel, Field # Field is used by some models
from typing import Optional, List, Dict # Keep Optional for type hints, Pydantic handles it
import json
import yaml
import re
import logging

from zenbi.mdl.loader import load_semantic_layer_from_data_dir #, generate_mdl_from_openmetadata # Commented out
from zenbi.mdl.models import SemanticLayer, ColumnDefinition, CalculatedColumnDefinition # These are already V2
from zenbi.core.config import settings, Settings # Settings is already V2
from zenbi.core.llm_service import LLMQueryService, serialize_mdl_for_llm
from zenbi.core.semantic_engine import SemanticEngine
from zenbi.core.database_service import DatabaseService
# from zenbi.core.openmetadata_service import OpenMetadataService # Commented out
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# --- Pydantic Models for API requests/responses (V2 style) ---
class ZenSQLQueryRequest(BaseModel):
    natural_language_query: str

class ZenSQLQueryResponse(BaseModel):
    natural_language_query: str
    zensql_query: str | None = None
    final_sql_query: str | None = None
    mdl_context_used: str | None = None
    query_results: List[Dict] | None = None
    chart_suggestion: Dict | None = None
    textual_insight: str | None = None
    error_message: str | None = None

class TranspileRequest(BaseModel):
    zensql_query: str
    target_dialect: str | None = "sqlite" # Using | None with default

class TranspileResponse(BaseModel):
    final_sql: str
    zensql_query: str
    target_dialect: str
    error_message: str | None = None

class SetupDbResponse(BaseModel):
    message: str
    tables_created: List[str] | None = None
    errors: List[str] | None = None

# class OpenMetadataImportRequest(BaseModel):
#     service_name: str = Field(..., description="Name of the service connector in OpenMetadata")
#     database_name: str = Field(..., description="Name of the database in OpenMetadata")
#     schema_name: str = Field(..., description="Name of the schema in OpenMetadata")

# class OpenMetadataImportResponse(BaseModel):
#     message: str
#     file_path: str | None = None
#     # mdl_content_summary is a dict, can be Dict | None
#     mdl_content_summary: Dict[str, int] | None = Field(default=None, description="Summary of imported MDL (e.g., number of models)")
#     error: str | None = None

# --- FastAPI App Initialization ---
app = FastAPI(
    title="ZenBI API",
    version="0.1.0",
    description="API for ZenBI"
)

# --- Global Services ---
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
            _semantic_layer_cache = load_semantic_layer_from_data_dir(file_name) # loader now uses model_validate
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

def parse_llm_output_for_chart_and_sql(raw_output: str) -> (Dict | None, str): # Updated type hint for chart_suggestion
    chart_suggestion: Dict | None = None # Explicitly type
    sql_query: str = raw_output.strip()
    match = re.search(r"/\* ZENBI_CHART_SUGGESTION_START\s*(\{.*?\})\s*ZENBI_CHART_SUGGESTION_END \*/", raw_output, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
        try:
            chart_suggestion = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Chart JSON parsing error: {e}. JSON: {json_str}")
            chart_suggestion = {"error": "Failed to parse chart JSON"} # Ensure chart_suggestion is a Dict if error
        sql_query = raw_output[match.end():].strip()
    return chart_suggestion, sql_query

# --- API Endpoints ---
@app.get("/", tags=["General"])
async def root(): return {"message": "Welcome to ZenBI"}

# @app.post("/admin/import-from-openmetadata", response_model=OpenMetadataImportResponse, tags=["Admin", "OpenMetadata"])
# async def import_from_openmetadata_endpoint(request: OpenMetadataImportRequest, app_settings: Settings = Depends(get_app_settings)):
#     # ... (OpenMetadata endpoint logic) ...
#     # This endpoint uses generate_mdl_from_openmetadata which returns SemanticLayer (V2 model)
#     # Then it uses semantic_layer.model_dump_json() which is V2.
#     # No changes needed here for Pydantic V2 other than request/response models already updated.
#     if not app_settings.OM_SERVER_URL: # Assuming OM_SERVER_URL is HttpUrl | None
#         raise HTTPException(status_code=400, detail="OpenMetadata integration is not configured (OM_SERVER_URL is not set).")

#     om_service: Optional[OpenMetadataService] = None
#     try:
#         om_service = OpenMetadataService(settings=app_settings) # Assuming OpenMetadataService handles Pydantic V2 if it uses models
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=f"Failed to initialize OpenMetadata service: {e}")
#     except Exception as e:
#         logger.error(f"OpenMetadata connection error: {e}")
#         raise HTTPException(status_code=503, detail="Failed to connect to OpenMetadata. Check server logs.")

#     try:
#         semantic_layer = generate_mdl_from_openmetadata(om_service, request.database_name, request.schema_name, request.service_name)
#         if not semantic_layer.models:
#             return OpenMetadataImportResponse(message="No models discovered.", mdl_content_summary={"models_count": 0})

#         data_dir = Path.cwd() / "zenbi" / "data"; data_dir.mkdir(parents=True, exist_ok=True)
#         file_name = f"generated_mdl_{request.service_name}_{request.database_name}_{request.schema_name}.yaml"
#         file_path = data_dir / file_name

#         # semantic_layer is already a Pydantic V2 model. model_dump_json() is the V2 way.
#         mdl_json_str = semantic_layer.model_dump_json(indent=2)
#         mdl_dict_for_yaml = json.loads(mdl_json_str) # Convert JSON string to Python dict for PyYAML

#         with open(file_path, 'w') as f:
#             yaml.dump(mdl_dict_for_yaml, f, sort_keys=False, allow_unicode=True)

#         return OpenMetadataImportResponse(
#             message="Import successful.",
#             file_path=str(file_path.relative_to(Path.cwd())),
#             mdl_content_summary={"models_count": len(semantic_layer.models)}
#         )
#     except Exception as e:
#         logger.error(f"Error during OpenMetadata import process: {e}")
#         raise HTTPException(status_code=500, detail=f"Error during import from OpenMetadata: {e}")


@app.get("/admin/setup-sample-db", response_model=SetupDbResponse, tags=["Admin"])
async def setup_sample_db_endpoint():
    # ... (No Pydantic model direct usage here that needs V1->V2 change) ...
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
    # Returns SemanticLayer, which is already a Pydantic V2 model
    return get_semantic_layer(file_name=file_name)


@app.post("/query/generate-zensql", response_model=ZenSQLQueryResponse, tags=["Query"])
async def generate_zensql_endpoint(request_body: ZenSQLQueryRequest, mdl_file_name: Optional[str] = "sample_mdl.yaml"): # Added type hint for request_body
    mdl_context = ""; zensql_query = ""; chart_suggestion: Optional[Dict] = None; error_msg = None # Type hint for chart_suggestion
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
async def transpile_zensql_endpoint(request_body: TranspileRequest, mdl_file_name: Optional[str] = "sample_mdl.yaml"): # Added type hint
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
async def execute_natural_language_query(request: ZenSQLQueryRequest, mdl_file_name: Optional[str] = "sample_mdl.yaml"): # Added type hint
    response_data = ZenSQLQueryResponse(natural_language_query=request.natural_language_query)

    try:
        if not llm_service:
            raise HTTPException(status_code=503, detail="LLM Service is not available due to configuration errors.")

        semantic_layer = get_semantic_layer(file_name=mdl_file_name)
        response_data.mdl_context_used = serialize_mdl_for_llm(semantic_layer)

        try:
            raw_llm_output = llm_service.generate_zensql(semantic_layer, request.natural_language_query)
            response_data.chart_suggestion, response_data.zensql_query = parse_llm_output_for_chart_and_sql(raw_llm_output)

            if not response_data.zensql_query and not (response_data.chart_suggestion and response_data.chart_suggestion.get("error")):
                err_msg = "LLM did not return a valid SQL query."
                if raw_llm_output and raw_llm_output.strip().startswith("-- Error"):
                    err_msg = raw_llm_output.strip()
                raise ValueError(err_msg)
        except Exception as e:
            logger.error(f"LLM Query Generation Error: {e}")
            response_data.error_message = f"LLM Query Generation Error: {str(e)}"
            return response_data

        try:
            semantic_engine = SemanticEngine(semantic_layer, target_dialect="sqlite")
            if response_data.zensql_query is None: # Should be caught by above, but defensive
                raise ValueError("ZenSQL query is missing for transpilation.")
            response_data.final_sql_query = semantic_engine.transpile_zensql_to_sql(response_data.zensql_query)
        except Exception as e:
            logger.error(f"SQL Transpilation Error: {e}")
            response_data.error_message = f"SQL Transpilation Error: {str(e)}"
            return response_data

        try:
            if response_data.final_sql_query is None: # Should be caught by above
                 raise ValueError("Final SQL query is missing for execution.")
            response_data.query_results = db_service.execute_query(response_data.final_sql_query)
        except SQLAlchemyError as e:
            logger.error(f"Database Execution Error: {e}")
            response_data.error_message = f"Database Execution Error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected Database Error: {e}")
            response_data.error_message = f"Unexpected Database Error: {str(e)}"

        if llm_service and response_data.final_sql_query :
            try:
                results_for_insight = response_data.query_results if response_data.query_results is not None else []
                response_data.textual_insight = llm_service.generate_textual_insight(
                    natural_language_query=request.natural_language_query,
                    final_sql_query=response_data.final_sql_query,
                    query_results=results_for_insight
                )
            except Exception as e:
                logger.error(f"Error generating textual insight: {e}")
                insight_error = f"Error generating textual insight: {str(e)}"
                if response_data.error_message: response_data.error_message += f"; {insight_error}"
                else: response_data.error_message = insight_error
        elif not response_data.error_message:
                 response_data.textual_insight = "Textual insight could not be generated due to missing SQL or LLM service unavailability."
    except HTTPException as e_http:
        raise e_http
    except Exception as e_global:
        logger.error(f"Global Error in execute_natural_language: {e_global}")
        if response_data.error_message: response_data.error_message += f"; Global error: {str(e_global)}"
        else: response_data.error_message = f"An unexpected error occurred: {str(e_global)}"

    return response_data
