import unittest
import sqlalchemy # For sqlalchemy.exc
from sqlalchemy import create_engine, inspect as sql_inspect, text
from zenbi.core.database_service import DatabaseService
from zenbi.mdl.models import SemanticLayer, ModelDefinition, ColumnDefinition, CalculatedColumnDefinition

# Helper to create a sample SemanticLayer for database tests
def create_db_test_semantic_layer() -> SemanticLayer:
    # Define models similar to sample_mdl.yaml but directly as Pydantic objects
    users_model = ModelDefinition(
        name="users",
        actual_table="actual_users_for_db_test", # Use distinct table names for test isolation
        columns=[
            ColumnDefinition(name="user_id", actual_name="id", dtype="INTEGER", description="User ID"),
            ColumnDefinition(name="name", actual_name="full_name", dtype="TEXT", description="User's name"),
            ColumnDefinition(name="city", actual_name="city_name", dtype="TEXT", description="User's city")
        ],
        primary_key="user_id"
    )
    orders_model = ModelDefinition(
        name="orders",
        actual_table="actual_orders_for_db_test",
        columns=[
            ColumnDefinition(name="order_id", actual_name="order_ref", dtype="INTEGER", description="Order ID"),
            ColumnDefinition(name="user_id", actual_name="customer_id", dtype="INTEGER", description="User ID (FK)"),
            ColumnDefinition(name="total_price", actual_name="order_total_amount", dtype="FLOAT", description="Order amount"),
            # Add a non-DB column (calculated) to ensure it's skipped during table creation
            CalculatedColumnDefinition(name="vat", actual_name="vat_calc", dtype="FLOAT", expression="total_price * 0.2")
        ],
        primary_key="order_id"
    )
    return SemanticLayer(models=[users_model, orders_model], relationships=[])


class TestDatabaseService(unittest.TestCase):
    db_url: str
    db_service: DatabaseService
    sample_semantic_layer: SemanticLayer

    @classmethod
    def setUpClass(cls):
        cls.db_url = "sqlite:///:memory:" # Use in-memory SQLite for tests
        cls.db_service = DatabaseService(db_url=cls.db_url)
        cls.sample_semantic_layer = create_db_test_semantic_layer()

        # Setup data once for the class if tests don't modify schema/data state in conflicting ways
        # If tests need pristine state, move setup_sample_data to setUp method
        cls.db_service.setup_sample_data(cls.sample_semantic_layer)

    def setUp(self):
        # If individual tests modify data and need a fresh start,
        # you might need to call setup_sample_data here or clean/re-insert data.
        # For now, assuming read-only tests or tests that don't interfere.
        pass


    def test_setup_sample_data_creates_tables_and_inserts_data(self):
        # Check if tables were created
        inspector = sql_inspect(self.db_service.engine)
        users_table_name = self.sample_semantic_layer.models[0].actual_table
        orders_table_name = self.sample_semantic_layer.models[1].actual_table

        self.assertTrue(inspector.has_table(users_table_name))
        self.assertTrue(inspector.has_table(orders_table_name))

        # Check if data was inserted (based on data from DatabaseService.setup_sample_data)
        # Note: DatabaseService.setup_sample_data uses hardcoded sample data.
        # This test should align with that specific sample data.

        # Users table checks (assuming DatabaseService inserts specific test data different from its main default)
        # For this test, let's assume setup_sample_data in DatabaseService was modified or can take data.
        # For now, we'll rely on the default data inserted by the current DatabaseService.setup_sample_data
        # (Alice, Bob, Charlie)
        users_data = self.db_service.execute_query(f"SELECT * FROM {users_table_name}")
        self.assertEqual(len(users_data), 3) # Assuming 3 users inserted by default
        self.assertEqual(users_data[0]['full_name'], "Alice Wonderland") # Check actual_name from model

        orders_data = self.db_service.execute_query(f"SELECT * FROM {orders_table_name}")
        self.assertEqual(len(orders_data), 4) # Assuming 4 orders inserted by default
        self.assertEqual(orders_data[0]['order_total_amount'], 150.75)

        # Check that calculated columns are not in the DB schema
        orders_cols = [col.name for col in inspector.get_columns(orders_table_name)]
        self.assertNotIn("vat", orders_cols) # 'vat' is semantic name of calc field
        self.assertNotIn("vat_calc", orders_cols) # 'vat_calc' is actual_name of calc field

    def test_execute_query_select_specific_user(self):
        users_table_name = self.sample_semantic_layer.models[0].actual_table
        # Assuming 'id' is the actual_name for user_id and 'Alice Wonderland' has id 1
        query = f"SELECT full_name FROM {users_table_name} WHERE id = 1"
        result = self.db_service.execute_query(query)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['full_name'], "Alice Wonderland")

    def test_execute_query_no_results(self):
        users_table_name = self.sample_semantic_layer.models[0].actual_table
        query = f"SELECT full_name FROM {users_table_name} WHERE id = 999" # Non-existent ID
        result = self.db_service.execute_query(query)
        self.assertEqual(len(result), 0)

    def test_execute_query_malformed_sql(self):
        # Test that execute_query correctly raises an SQLAlchemyError (or subclass) for bad SQL
        with self.assertRaises(sqlalchemy.exc.SQLAlchemyError):
            self.db_service.execute_query("SELECT MALFORMED SQL FROM some_table")

    def test_table_exists_method(self):
        users_table_name = self.sample_semantic_layer.models[0].actual_table
        self.assertTrue(self.db_service.table_exists(users_table_name))
        self.assertFalse(self.db_service.table_exists("non_existent_table_for_test"))

    @classmethod
    def tearDownClass(cls):
        # Optional: Clean up the in-memory database if needed, though :memory: is ephemeral.
        # For file-based test DBs, this would be where you remove the file.
        # cls.db_service.engine.dispose() # Not strictly necessary for :memory:
        pass

if __name__ == '__main__':
    unittest.main()
