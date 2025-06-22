import yaml
from pathlib import Path
from zenbi.mdl.models import SemanticLayer, ModelDefinition
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from zenbi.core.openmetadata_service import OpenMetadataService


def load_semantic_layer_from_yaml(file_path: str) -> SemanticLayer:
    """
    Reads a YAML file, parses it, and validates it against the SemanticLayer Pydantic model.
    """
    abs_file_path = Path(file_path).resolve()
    if not abs_file_path.exists():
        raise FileNotFoundError(f"MDL YAML file not found at {abs_file_path}")

    with open(abs_file_path, 'r') as f:
        data = yaml.safe_load(f)

    # Pydantic V2 way to validate data from a dictionary
    return SemanticLayer.model_validate(data)

def load_semantic_layer_from_data_dir(file_name: str) -> SemanticLayer:
    """
    Loads a semantic layer from a YAML file located in the 'zenbi/data' directory.
    """
    current_script_dir = Path(__file__).parent
    project_root_approx = current_script_dir.parent.parent
    data_dir = project_root_approx / "zenbi" / "data"

    file_path = data_dir / file_name
    if not file_path.exists():
        alt_data_dir = Path.cwd() / "zenbi" / "data"
        alt_file_path = alt_data_dir / file_name
        if alt_file_path.exists():
            file_path = alt_file_path
        else:
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

    return SemanticLayer(
        models=discovered_models,
        relationships=[]
    )
