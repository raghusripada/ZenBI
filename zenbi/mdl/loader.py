import yaml
from pathlib import Path
from zenbi.mdl.models import SemanticLayer, ModelDefinition # Added ModelDefinition
from typing import TYPE_CHECKING, List # Added List and TYPE_CHECKING

if TYPE_CHECKING:
    from zenbi.core.openmetadata_service import OpenMetadataService


def load_semantic_layer_from_yaml(file_path: str) -> SemanticLayer:
    """
    Reads a YAML file, parses it, and validates it against the SemanticLayer Pydantic model.
    """
    # Ensure file_path is an absolute path or correctly relative to the execution context
    abs_file_path = Path(file_path).resolve()
    if not abs_file_path.exists():
        raise FileNotFoundError(f"MDL YAML file not found at {abs_file_path}")

    with open(abs_file_path, 'r') as f:
        data = yaml.safe_load(f)
    return SemanticLayer(**data)

def load_semantic_layer_from_data_dir(file_name: str) -> SemanticLayer:
    """
    Loads a semantic layer from a YAML file located in the 'zenbi/data' directory.
    Assumes 'zenbi/data' is at the project root level relative to where the app runs,
    or that this function is called from a context where Path resolution works as intended.
    """
    # Path(__file__) gives path to this loader.py file.
    # Parent of zenbi/mdl/loader.py is zenbi/mdl/. Parent of that is zenbi/.
    # So, zenbi/data is at current_dir.parent / "data"
    current_script_dir = Path(__file__).parent
    project_root_approx = current_script_dir.parent.parent # Assuming zenbi/mdl/loader.py, this goes to project root
    data_dir = project_root_approx / "zenbi" / "data" # More robust path construction

    # A common pattern is to have a single 'data' dir at the project root:
    # project_root = Path.cwd() # Or some other way to define project root
    # data_dir = project_root / "data"
    # For now, stick to relative path from this file, assuming a standard project structure.

    file_path = data_dir / file_name
    if not file_path.exists():
         # Fallback for cases where PWD might be project root
        alt_data_dir = Path.cwd() / "zenbi" / "data"
        alt_file_path = alt_data_dir / file_name
        if alt_file_path.exists():
            file_path = alt_file_path
        else:
            # Original error if neither path works
            raise FileNotFoundError(f"MDL file '{file_name}' not found in default data directory: {file_path} or {alt_file_path}")

    return load_semantic_layer_from_yaml(str(file_path))


def generate_mdl_from_openmetadata(
    om_service: 'OpenMetadataService',
    database_name: str,
    schema_name: str,
    service_name: str
) -> SemanticLayer:
    """
    Generates a SemanticLayer object by discovering models from OpenMetadata.
    Relationships are not discovered by this function.
    """
    print(f"Attempting to discover models from OpenMetadata: service='{service_name}', database='{database_name}', schema='{schema_name}'")
    discovered_models: List[ModelDefinition] = om_service.discover_models_from_schema(
        database_name=database_name,
        schema_name=schema_name,
        service_name=service_name
    )

    if not discovered_models:
        print(f"No models discovered from OpenMetadata for {service_name}.{database_name}.{schema_name}")
    else:
        print(f"Discovered {len(discovered_models)} models.")
        for model_def in discovered_models:
            print(f"  - Model: {model_def.name}, Columns: {len(model_def.columns)}")

    # Create a SemanticLayer object with the discovered models and empty relationships
    return SemanticLayer(
        models=discovered_models,
        relationships=[] # Relationships would need separate discovery logic
    )
