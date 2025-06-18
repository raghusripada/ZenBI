from typing import Optional, List, Dict as TypingDict

from metadata.generated.schema.entity.data.table import Table, DataType
from metadata.generated.schema.entity.services.connections.metadata.openMetadataConnection import OpenMetadataConnection, AuthProvider
from metadata.generated.schema.security.client.openMetadataJWTClientConfig import OpenMetadataJWTClientConfig
from metadata.generated.schema.security.client.googleSSOClientConfig import GoogleSSOClientConfig
from metadata.ingestion.ometa.ometa_api import OMetaAPI

from zenbi.core.config import Settings
from zenbi.mdl.models import ModelDefinition, ColumnDefinition # SemanticLayer not directly used here but good for context

class OpenMetadataService:
    def __init__(self, settings: Settings):
        self.settings = settings
        if not self.settings.OM_SERVER_URL:
            raise ValueError("OpenMetadata server URL (OM_SERVER_URL) is not configured.")

        auth_provider_instance: Optional[AuthProvider] = None
        security_config: Optional[TypingDict] = None # OMetaAPI expects securityConfig as a dict

        if self.settings.OM_AUTH_PROVIDER == "no-auth":
            auth_provider_instance = AuthProvider.no_auth
        elif self.settings.OM_AUTH_PROVIDER == "openmetadata":
            if not self.settings.OM_JWT_TOKEN:
                raise ValueError("OM_JWT_TOKEN must be provided for 'openmetadata' auth provider.")
            # For OMetaAPI, securityConfig for JWT is OpenMetadataJWTClientConfig
            security_config = OpenMetadataJWTClientConfig(jwtToken=self.settings.OM_JWT_TOKEN)
            auth_provider_instance = AuthProvider.openmetadata_jwt
        elif self.settings.OM_AUTH_PROVIDER == "google":
            if not self.settings.OM_SECRET_KEY: # Assuming OM_SECRET_KEY holds the path to JSON or the JSON string itself
                raise ValueError("OM_SECRET_KEY must be provided for 'google' auth provider.")
            # For OMetaAPI, securityConfig for Google is GoogleSSOClientConfig
            # The OM SDK has evolved; GoogleCredentials was for older versions or specific ingestion paths.
            # GoogleSSOClientConfig is more common for direct API client auth with service accounts.
            # It expects the secret key content or path.
            security_config = GoogleSSOClientConfig(secretKey=self.settings.OM_SECRET_KEY)
            auth_provider_instance = AuthProvider.google #This might need adjustment based on exact SDK expectations for client
        else:
            raise ValueError(f"Unsupported OpenMetadata auth provider: {self.settings.OM_AUTH_PROVIDER}")

        try:
            # OpenMetadataConnection expects hostPort as a string like "http://localhost:8585" (without /api)
            # but settings.OM_SERVER_URL is HttpUrl, which includes /api. We need to strip /api.
            host_port = str(self.settings.OM_SERVER_URL).replace("/api", "")

            connection_config = OpenMetadataConnection(
                hostPort=host_port,
                authProvider=auth_provider_instance,
                securityConfig=security_config,
                # apiEndpoint=str(self.settings.OM_SERVER_URL), # some versions might use this
                # verifySSL="ignore" # if using self-signed certs for OM
            )
            self.metadata_client = OMetaAPI(connection_config)
            # Test connection by fetching server config or a simple entity
            self.metadata_client.health_check()
            print("Successfully connected to OpenMetadata server.")

        except Exception as e:
            print(f"Failed to connect to OpenMetadata: {e}")
            raise ValueError(f"OpenMetadata connection failed: {e}") from e

    _OM_TYPE_MAP = {
        DataType.STRING.value: "TEXT",
        DataType.TEXT.value: "TEXT",
        DataType.INT.value: "INTEGER",
        DataType.BIGINT.value: "INTEGER", # Assuming BIGINT maps to standard INTEGER for MDL simplicity
        DataType.SMALLINT.value: "INTEGER",
        DataType.TINYINT.value: "INTEGER",
        DataType.FLOAT.value: "FLOAT",
        DataType.DOUBLE.value: "FLOAT",
        DataType.DECIMAL.value: "FLOAT", # Or a more specific NUMERIC/DECIMAL type if MDL supports
        DataType.NUMBER.value: "FLOAT", # Generic number, map to FLOAT
        DataType.BOOLEAN.value: "BOOLEAN", # Add BOOLEAN to MDL if not present, else TEXT
        DataType.TIMESTAMP.value: "TIMESTAMP",
        DataType.DATE.value: "DATE", # Add DATE to MDL if not present, else TEXT
        DataType.TIME.value: "TIME", # Add TIME to MDL if not present, else TEXT
        DataType.DATETIME.value: "TIMESTAMP", # DATETIME is often same as TIMESTAMP
        DataType.JSON.value: "TEXT", # Represent JSON as TEXT in MDL
        DataType.UUID.value: "TEXT", # UUIDs are typically strings
        # Add other mappings as necessary
    }

    def _map_om_dtype_to_mdl_dtype(self, om_dtype_value: str) -> str:
        return self._OM_TYPE_MAP.get(om_dtype_value.upper(), "TEXT") # Default to TEXT

    def get_table_metadata(self, database_fqn: str, schema_fqn_part: str, table_name: str, service_name: str) -> Optional[ModelDefinition]:
        """
        Fetches metadata for a single table from OpenMetadata.
        database_fqn: FQN of the database (e.g., service_name.database_name)
        schema_fqn_part: Just the schema name (e.g., public_schema)
        table_name: Name of the table (e.g., raw_orders)
        service_name: Name of the service connector in OpenMetadata (e.g., local_postgres)
        """
        # Construct the FQN for the table. OM FQN for table is service.db.schema.table
        table_fqn = f"{service_name}.{database_fqn}.{schema_fqn_part}.{table_name}"

        try:
            table_entity: Optional[Table] = self.metadata_client.get_by_name(
                entity=Table,
                fqn=table_fqn,
                fields=["columns", "tableConstraints", "owner", "databaseSchema", "database", "description"]
            )

            if table_entity and table_entity.columns:
                mdl_columns: List[ColumnDefinition] = []
                for col in table_entity.columns:
                    col_description = col.description.root if col.description else None
                    mdl_columns.append(
                        ColumnDefinition(
                            name=col.name.root, # OM names are often roots
                            actual_name=col.name.root, # Assume semantic name matches actual for initial import
                            dtype=self._map_om_dtype_to_mdl_dtype(str(col.dataType.value)),
                            description=col_description,
                            # properties: Optional[dict] = None # Can extract OM tags/properties here
                        )
                    )

                table_description = table_entity.description.root if table_entity.description else None

                # Extract primary key if available
                primary_key_semantic_name: Optional[str] = None
                if table_entity.tableConstraints:
                    for constraint in table_entity.tableConstraints:
                        if constraint.constraintType == "PRIMARY_KEY":
                            if constraint.columns:
                                # Assuming single column PK for simplicity in MDL model's primary_key field
                                primary_key_semantic_name = constraint.columns[0].root
                                break

                return ModelDefinition(
                    name=table_entity.name.root, # Use table name as semantic name
                    actual_table=table_entity.name.root, # Actual table name
                    description=table_description,
                    columns=mdl_columns,
                    primary_key=primary_key_semantic_name
                    # Add other ModelDefinition fields if they can be mapped from OM
                )
            else:
                print(f"Table not found or has no columns: {table_fqn}")
                return None
        except Exception as e:
            print(f"Error fetching table metadata for {table_fqn}: {e}")
            return None

    def discover_models_from_schema(self, database_name: str, schema_name: str, service_name: str) -> List[ModelDefinition]:
        """
        Discovers all tables in a given schema and returns them as a list of ModelDefinition objects.
        database_name: Name of the database (e.g., sample_data)
        schema_name: Name of the schema (e.g., public)
        service_name: Name of the service connector (e.g., local_postgres)
        """
        # In OM, database FQN is serviceName.dbName
        # Schema FQN is serviceName.dbName.schemaName
        db_fqn_for_schema_param = f"{service_name}.{database_name}"
        schema_fqn_for_listing = f"{service_name}.{database_name}.{schema_name}"

        models: List[ModelDefinition] = []
        try:
            # List tables in the schema. The `databaseSchema` parameter for list_entities expects FQN of the schema.
            # The `database` parameter expects FQN of the database.
            # It's often easier to list all tables for a database and then filter by schema client-side if direct schema filtering is tricky.
            # However, let's try with `databaseSchema` first.

            # list_entities for tables usually requires `database` (FQN of database) to narrow down search
            # and then we can check `table.databaseSchema.fullyQualifiedName`
            all_tables_in_db = self.metadata_client.list_entities(
                entity=Table,
                params={"database": db_fqn_for_schema_param}, # FQN of the database
                fields=["columns", "databaseSchema", "database", "description", "tableConstraints"] # ensure all needed fields
            )

            if all_tables_in_db and all_tables_in_db.entities:
                for table_entity in all_tables_in_db.entities:
                    if table_entity.databaseSchema and table_entity.databaseSchema.fullyQualifiedName.root == schema_fqn_for_listing:
                        # Now correctly get metadata for this specific table
                        # table_entity.name.root is just the table name, not FQN
                        # We need to pass the components to get_table_metadata

                        model_def = self.get_table_metadata(
                            database_fqn=database_name, # just db name part for context
                            schema_fqn_part=schema_name, # just schema name part
                            table_name=table_entity.name.root,
                            service_name=service_name
                        )
                        if model_def:
                             models.append(model_def)
            else:
                print(f"No tables found in database {db_fqn_for_schema_param} or error listing entities.")

        except Exception as e:
            print(f"Error discovering models from schema {schema_fqn_for_listing}: {e}")

        return models
