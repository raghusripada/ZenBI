from typing import List, Optional, Union, Dict # Keep Union for list items
from pydantic import BaseModel, Field # Import Field

class ColumnDefinition(BaseModel):
    name: str  # semantic name
    actual_name: str  # database column name
    dtype: str  # e.g., "TEXT", "INTEGER", "FLOAT", "TIMESTAMP"
    description: str | None = None  # Pydantic V2 style for Optional: type | None
    properties: Dict | None = Field(default_factory=dict) # Use default_factory for mutable dict

class CalculatedColumnDefinition(ColumnDefinition):
    expression: str  # SQL expression using other semantic column names from the same model

class RelationshipDefinition(BaseModel):
    name: str
    from_model: str  # semantic name of the source model
    to_model: str  # semantic name of the target model
    from_columns: List[str]
    to_columns: List[str]
    type: str  # e.g., "ONE_TO_MANY", "MANY_TO_ONE", "ONE_TO_ONE", "MANY_TO_MANY"
    description: str | None = None # Pydantic V2 style

class ModelDefinition(BaseModel):
    name: str  # semantic name
    actual_table: str  # database table/view name
    description: str | None = None
    # For list of union types, Pydantic V2 handles this well.
    # We need to ensure that the parsing logic correctly uses discriminated unions if needed,
    # but for definition, this is fine.
    columns: List[Union[ColumnDefinition, CalculatedColumnDefinition]]
    primary_key: str | None = None  # semantic name of PK column

class SemanticLayer(BaseModel):
    models: List[ModelDefinition]
    relationships: List[RelationshipDefinition]

    # Example of a V2 model dump method if needed elsewhere, not strictly required for the model itself
    # def to_yaml_str(self) -> str:
    #     import yaml
    #     return yaml.dump(self.model_dump(mode='python'), sort_keys=False, allow_unicode=True)

    # Example of a V2 model validation method if needed elsewhere
    # @classmethod
    # def from_yaml_str(cls, yaml_str: str) -> 'SemanticLayer':
    #     import yaml
    #     data = yaml.safe_load(yaml_str)
    #     return cls.model_validate(data)
