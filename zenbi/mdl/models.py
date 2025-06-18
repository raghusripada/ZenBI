from typing import List, Optional, Union, Dict
from pydantic import BaseModel

class ColumnDefinition(BaseModel):
    name: str  # semantic name
    actual_name: str  # database column name
    dtype: str  # e.g., "TEXT", "INTEGER", "FLOAT", "TIMESTAMP"
    description: Optional[str] = None
    properties: Optional[Dict] = None  # for things like displayName

class CalculatedColumnDefinition(ColumnDefinition):
    expression: str  # SQL expression using other semantic column names from the same model

class RelationshipDefinition(BaseModel):
    name: str
    from_model: str  # semantic name of the source model
    to_model: str  # semantic name of the target model
    from_columns: List[str]  # semantic column names in source model for join
    to_columns: List[str]  # semantic column names in target model for join
    type: str  # e.g., "ONE_TO_MANY", "MANY_TO_ONE", "ONE_TO_ONE", "MANY_TO_MANY"

class ModelDefinition(BaseModel):
    name: str  # semantic name
    actual_table: str  # database table/view name
    description: Optional[str] = None
    columns: List[Union[ColumnDefinition, CalculatedColumnDefinition]]
    primary_key: Optional[str] = None  # semantic name of PK column

class SemanticLayer(BaseModel):
    models: List[ModelDefinition]
    relationships: List[RelationshipDefinition]
