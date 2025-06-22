import sqlalchemy
from sqlalchemy import create_engine, text, Table, Column, Integer, String, Float, MetaData, DateTime, inspect
from zenbi.mdl.models import SemanticLayer, ModelDefinition, ColumnDefinition, CalculatedColumnDefinition
from typing import List, Dict

class DatabaseService:
    def __init__(self, db_url: str = "sqlite:///./zenbi_data.db"):
        self.engine = create_engine(db_url)
        self.metadata = MetaData()

    def _mdl_dtype_to_sqla(self, mdl_dtype: str):
        # Basic type mapping, can be expanded
        if mdl_dtype.upper() == "INTEGER":
            return Integer
        elif mdl_dtype.upper() == "TEXT" or mdl_dtype.upper() == "STRING": # Added STRING
            return String
        elif mdl_dtype.upper() == "FLOAT":
            return Float
        elif mdl_dtype.upper() == "TIMESTAMP" or mdl_dtype.upper() == "DATETIME": # Added DATETIME
            return DateTime
        else:
            return String # Default type

    def setup_sample_data(self, semantic_layer: SemanticLayer):
        # Ensure tables are fresh by dropping existing ones defined in the metadata
        # This makes the setup idempotent by starting clean each time.
        # inspect(self.engine).get_table_names() can get all table names if needed for more selective dropping.

        # Reflect existing tables to handle selective drop if necessary or to check existence
        self.metadata.reflect(bind=self.engine)

        for model in reversed(semantic_layer.models): # Drop in reverse order of creation due to FKs (if any)
            actual_table_name = model.actual_table
            if actual_table_name in self.metadata.tables:
                table_to_drop = self.metadata.tables[actual_table_name]
                print(f"Dropping existing table: {actual_table_name}")
                try:
                    table_to_drop.drop(self.engine)
                except Exception as e:
                    print(f"Error dropping table {actual_table_name}: {e}")


        # After potentially dropping, clear the metadata for recreation
        self.metadata.clear()

        # Create tables
        for model in semantic_layer.models:
            actual_table_name = model.actual_table
            if actual_table_name not in self.metadata.tables:
                print(f"Defining table: {actual_table_name}")
                sqla_columns = []
                for col_def in model.columns:
                    if isinstance(col_def, ColumnDefinition): # Only map non-calculated columns to DB schema
                        sqla_type = self._mdl_dtype_to_sqla(col_def.dtype)
                        is_primary_key = (col_def.name == model.primary_key)
                        sqla_columns.append(
                            Column(col_def.actual_name, sqla_type, primary_key=is_primary_key)
                        )

                if not sqla_columns: # Should not happen with valid MDL
                    print(f"Warning: No direct columns to create for table {actual_table_name}")
                    continue

                Table(actual_table_name, self.metadata, *sqla_columns)
            else:
                print(f"Table {actual_table_name} already defined in metadata (should not happen after clear).")

        self.metadata.create_all(self.engine)
        print("All tables created based on semantic layer.")

        # Insert sample data
        with self.engine.connect() as connection:
            # Sample Users
            users_model = next((m for m in semantic_layer.models if m.name == "users"), None)
            if users_model:
                users_table = self.metadata.tables.get(users_model.actual_table)
                if users_table is not None:
                    # Check if data exists before inserting to avoid duplicate primary key errors
                    if connection.execute(users_table.select().limit(1)).first() is None:
                        print(f"Inserting sample data into {users_model.actual_table}")
                        connection.execute(users_table.insert(), [
                            {"id": 1, "email_address": "alice@example.com", "full_name": "Alice Wonderland", "city_name": "New York"},
                            {"id": 2, "email_address": "bob@example.com", "full_name": "Bob The Builder", "city_name": "London"},
                            {"id": 3, "email_address": "charlie@example.com", "full_name": "Charlie Chaplin", "city_name": "Paris"},
                        ])
                    else:
                        print(f"Sample data already exists in {users_model.actual_table}")
                else:
                    print(f"Could not find table {users_model.actual_table} in metadata for data insertion.")

            # Sample Orders
            orders_model = next((m for m in semantic_layer.models if m.name == "orders"), None)
            if orders_model:
                orders_table = self.metadata.tables.get(orders_model.actual_table)
                if orders_table is not None:
                    if connection.execute(orders_table.select().limit(1)).first() is None:
                        print(f"Inserting sample data into {orders_model.actual_table}")
                        connection.execute(orders_table.insert(), [
                            {"order_ref": 101, "customer_id": 1, "date_of_order": "2023-01-15T10:00:00", "order_total_amount": 150.75, "order_amount_eur": 140.20, "number_of_items": 2},
                            {"order_ref": 102, "customer_id": 1, "date_of_order": "2023-02-20T14:30:00", "order_total_amount": 75.50, "order_amount_eur": 70.00, "number_of_items": 1},
                            {"order_ref": 103, "customer_id": 2, "date_of_order": "2023-03-10T09:15:00", "order_total_amount": 200.00, "order_amount_eur": 185.50, "number_of_items": 5},
                            {"order_ref": 104, "customer_id": 3, "date_of_order": "2023-04-05T11:00:00", "order_total_amount": 50.25, "order_amount_eur": 46.70, "number_of_items": 1},
                        ])
                    else:
                        print(f"Sample data already exists in {orders_model.actual_table}")
                else:
                    print(f"Could not find table {orders_model.actual_table} in metadata for data insertion.")

            connection.commit()
        print("Sample data setup complete.")


    def execute_query(self, sql_query: str) -> List[Dict]:
        with self.engine.connect() as connection:
            try:
                result = connection.execute(text(sql_query))
                # For SQLAlchemy 2.0, mappings().all() returns a list of RowMapping objects
                # which behave like dictionaries. Each row can be converted with _asdict().
                results_as_dicts = [row._asdict() for row in result.mappings().all()]
                # No explicit commit for SELECT, but if the query was DML/DDL it would be needed.
                # connection.commit() # Not strictly needed for SELECTs on most backends with autocommit.
                return results_as_dicts
            except sqlalchemy.exc.SQLAlchemyError as e:
                print(f"Error executing query: {sql_query}\nError: {e}")
                # connection.rollback() # Rollback in case of error if transactions were involved.
                raise # Re-raise the exception to be handled by the caller

    def table_exists(self, table_name: str) -> bool:
        """Checks if a table exists in the database."""
        inspector = inspect(self.engine)
        return inspector.has_table(table_name)

# Example usage:
if __name__ == '__main__':
    # This part would require a sample SemanticLayer object.
    # For now, just test basic connection and table creation manually if needed.
    print("DatabaseService module loaded. Example usage requires SemanticLayer instance.")
    # db_service = DatabaseService("sqlite:///./test_db_service.db")
    # print(f"Using database: {db_service.engine.url}")
    # Manually create a test table
    # test_table = Table(
    #     "test_manual_table", db_service.metadata,
    #     Column("id", Integer, primary_key=True),
    #     Column("name", String)
    # )
    # db_service.metadata.create_all(db_service.engine)
    # print("Manual test table created if it didn't exist.")
    # db_service.execute_query("INSERT INTO test_manual_table (id, name) VALUES (1, 'Test Entry') ON CONFLICT(id) DO NOTHING")
    # results = db_service.execute_query("SELECT * FROM test_manual_table")
    # print("Results from manual test table:", results)
