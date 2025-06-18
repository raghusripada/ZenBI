import unittest
import yaml
from pathlib import Path
from zenbi.core.semantic_engine import SemanticEngine
from zenbi.mdl.models import SemanticLayer, ModelDefinition, ColumnDefinition, CalculatedColumnDefinition
from zenbi.mdl.loader import load_semantic_layer_from_yaml
import sqlglot # For ParseError

# Helper to load the sample MDL for tests
def load_test_semantic_layer(file_name="sample_mdl.yaml") -> SemanticLayer:
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent
    mdl_file_path = project_root / "zenbi" / "data" / file_name

    if not mdl_file_path.exists():
        # Try an alternative path if running tests from project root
        alt_mdl_file_path = Path.cwd() / "zenbi" / "data" / file_name
        if alt_mdl_file_path.exists():
            mdl_file_path = alt_mdl_file_path
        else:
            raise FileNotFoundError(f"Test MDL file not found at {mdl_file_path} or {alt_mdl_file_path}")

    return load_semantic_layer_from_yaml(str(mdl_file_path))

class TestSemanticEngine(unittest.TestCase):
    semantic_layer: SemanticLayer

    @classmethod
    def setUpClass(cls):
        cls.semantic_layer = load_test_semantic_layer() # Loads from sample_mdl.yaml

        # --- Modifications for specific tests ---
        orders_model = next((m for m in cls.semantic_layer.models if m.name == "orders"), None)
        if orders_model:
            # Ensure base column 'total_price' exists (it's in sample_mdl.yaml)
            total_price_col = next((c for c in orders_model.columns if c.name == "total_price"), None)
            if not total_price_col:
                # This should not happen if sample_mdl.yaml is correct
                raise ValueError("Base column 'total_price' not found in orders model for test setup.")

            # Add 'vat_amount' (total_price * 0.2) - already added in API get_semantic_layer, but good to ensure here
            if not any(c.name == "vat_amount" for c in orders_model.columns):
                vat_column = CalculatedColumnDefinition(
                    name="vat_amount", actual_name="vat_calc", dtype="FLOAT",
                    expression="total_price * 0.20", description="VAT calculated at 20% of order total"
                )
                orders_model.columns.append(vat_column)

            # Add 'price_with_vat' (total_price + vat_amount) for testing calc field referencing another calc field
            # Note: The SemanticEngine's current _transform_node for calculated columns might need to be robust enough
            # to handle nested calculated fields if 'vat_amount' itself is used in the expression.
            # For this test, the expression for price_with_vat will refer to semantic names,
            # one of which ('vat_amount') is a calculated field.
            # The engine should resolve 'vat_amount' to its expression first.
            if not any(c.name == "price_with_vat" for c in orders_model.columns):
                price_with_vat_column = CalculatedColumnDefinition(
                    name="price_with_vat", actual_name="price_inc_vat", dtype="FLOAT",
                    expression="total_price + vat_amount",
                    description="Total price including VAT (total_price + total_price * 0.2)"
                )
                orders_model.columns.append(price_with_vat_column)
        else:
            raise ValueError("Orders model not found in semantic layer for test setup.")

        users_model = next((m for m in cls.semantic_layer.models if m.name == "users"), None)
        if users_model:
            # Ensure 'city' and 'name' columns exist for other tests (they are in sample_mdl.yaml)
            if not any(c.name == "city" for c in users_model.columns):
                 users_model.columns.append(ColumnDefinition(name="city", actual_name="city_name", dtype="TEXT"))
            if not any(c.name == "name" for c in users_model.columns):
                 users_model.columns.append(ColumnDefinition(name="name", actual_name="full_name", dtype="TEXT"))
        else:
            raise ValueError("Users model not found for test setup.")

        # Standard engine for most tests
        cls.engine_sqlite = SemanticEngine(cls.semantic_layer, target_dialect="sqlite")


    def test_simple_select_direct_mapping(self):
        zensql = "SELECT user_id, email FROM users"
        # sample_mdl.yaml: users.user_id -> id, users.email -> email_address
        expected_sql = "SELECT id, email_address FROM actual_users_table"
        self.assertEqual(self.engine_sqlite.transpile_zensql_to_sql(zensql).replace("\n", " ").strip(), expected_sql.strip())

    def test_query_with_table_alias(self):
        zensql = "SELECT u.email FROM users u WHERE u.city = 'New York'"
        # sample_mdl.yaml: users.email -> email_address, users.city -> city_name
        expected_sql = "SELECT u.email_address FROM actual_users_table AS u WHERE u.city_name = 'New York'"
        self.assertEqual(self.engine_sqlite.transpile_zensql_to_sql(zensql).replace("\n", " ").strip(), expected_sql.strip())

    def test_calculated_field_basic(self):
        # 'vat_amount' is 'total_price * 0.20'
        # sample_mdl.yaml: orders.order_id -> order_ref, orders.total_price -> order_total_amount
        zensql = "SELECT order_id, vat_amount FROM orders"
        expected_sql = "SELECT order_ref, order_total_amount * 0.2 AS vat_amount FROM actual_orders_table"
        self.assertEqual(self.engine_sqlite.transpile_zensql_to_sql(zensql).replace("\n", " ").strip(), expected_sql.strip())

    def test_calculated_field_with_table_alias(self):
        zensql = "SELECT o.order_id, o.vat_amount FROM orders o"
        expected_sql = "SELECT o.order_ref, o.order_total_amount * 0.2 AS vat_amount FROM actual_orders_table AS o"
        self.assertEqual(self.engine_sqlite.transpile_zensql_to_sql(zensql).replace("\n", " ").strip(), expected_sql.strip())

    def test_join_query(self):
        zensql = "SELECT u.name, o.order_date FROM users u JOIN orders o ON u.user_id = o.user_id"
        # sample_mdl.yaml: users.name -> full_name, orders.order_date -> date_of_order
        # users.user_id -> id, orders.user_id -> customer_id
        expected_sql = "SELECT u.full_name, o.date_of_order FROM actual_users_table AS u JOIN actual_orders_table AS o ON u.id = o.customer_id"
        self.assertEqual(self.engine_sqlite.transpile_zensql_to_sql(zensql).replace("\n", " ").strip(), expected_sql.strip())

    def test_unqualified_columns_single_table_scope(self):
        zensql = "SELECT user_id, email, city FROM users WHERE city = 'London'"
        expected_sql = "SELECT id, email_address, city_name FROM actual_users_table WHERE city_name = 'London'"
        self.assertEqual(self.engine_sqlite.transpile_zensql_to_sql(zensql).replace("\n", " ").strip(), expected_sql.strip())

    def test_calculated_field_referencing_calculated_field(self):
        # price_with_vat = total_price + vat_amount
        # vat_amount = total_price * 0.20
        # So, price_with_vat should expand to: total_price + (total_price * 0.20)
        # Actual names: order_total_amount for total_price
        zensql = "SELECT order_id, price_with_vat FROM orders"
        # SQLGlot might produce slightly different but equivalent expressions, e.g. total_price * 1.2
        # The current engine resolves vat_amount first, then substitutes its expression.
        # So it should be: order_total_amount + (order_total_amount * 0.2) AS price_with_vat
        # Let's verify this based on engine's logic.
        expected_sql = "SELECT order_ref, order_total_amount + order_total_amount * 0.2 AS price_with_vat FROM actual_orders_table"
        # print("DEBUG CALC ON CALC: ", self.engine_sqlite.transpile_zensql_to_sql(zensql))
        self.assertEqual(self.engine_sqlite.transpile_zensql_to_sql(zensql).replace("\n", " ").strip(), expected_sql.strip())


    def test_transpile_to_postgres_dialect(self):
        engine_pg = SemanticEngine(self.semantic_layer, target_dialect="postgres")
        zensql = "SELECT user_id FROM users"
        # For Postgres, SQLGlot by default quotes identifiers if they are case-sensitive or keywords.
        # 'id' and 'actual_users_table' are not keywords and typically don't require quotes unless forced.
        # SQLGlot's default behavior for postgres might not quote these simple names.
        # Let's check actual output of SQLGlot for postgres with simple identifiers.
        # sqlglot.parse_one("SELECT id FROM actual_users_table").sql("postgres") -> 'SELECT id FROM actual_users_table'
        # So, no quotes for these simple names by default.
        expected_sql_pg = 'SELECT id FROM actual_users_table' # users.user_id -> id

        # If we had a column like "User Name" (with space), then PG would quote: "User Name"
        # Or a table like "My Table", then "My Table".
        # Our current actual names are simple.
        self.assertEqual(engine_pg.transpile_zensql_to_sql(zensql).replace("\n", " ").strip(), expected_sql_pg.strip())

    def test_error_handling_for_zensql_parse_error(self):
        # Conceptual: Test that SemanticEngine.transpile_zensql_to_sql raises an error
        # (specifically ValueError, as it wraps sqlglot.errors.ParseError)
        # if sqlglot.parse_one fails.
        invalid_zensql = "SELECT FROM WHERE NONSENSE" # This is syntactically incorrect
        with self.assertRaisesRegex(ValueError, "Error parsing ZenSQL query"):
            self.engine_sqlite.transpile_zensql_to_sql(invalid_zensql)

        # Also test if it's specifically a sqlglot.errors.ParseError that's caught and wrapped.
        # This requires a bit more introspection or ensuring the ValueError message contains ParseError details.
        # The current regex "Error parsing ZenSQL query" checks our wrapper's message.

if __name__ == "__main__":
    unittest.main()
