import unittest
from unittest.mock import patch, MagicMock
from zenbi.core.llm_service import LLMQueryService, serialize_mdl_for_llm
from zenbi.core.config import Settings
from zenbi.mdl.models import SemanticLayer, ModelDefinition, ColumnDefinition, CalculatedColumnDefinition, RelationshipDefinition
from typing import List

# Helper to create a sample SemanticLayer for testing
def create_sample_semantic_layer() -> SemanticLayer:
    users_model = ModelDefinition(
        name="users",
        actual_table="actual_users",
        columns=[
            ColumnDefinition(name="user_id", actual_name="id", dtype="INTEGER", description="User ID"),
            ColumnDefinition(name="name", actual_name="full_name", dtype="TEXT", description="User's full name"),
            CalculatedColumnDefinition(
                name="name_upper", actual_name="name_upper_calc", dtype="TEXT",
                expression="UPPER(name)", description="Uppercase user name"
            )
        ],
        primary_key="user_id"
    )
    orders_model = ModelDefinition(
        name="orders",
        actual_table="actual_orders",
        columns=[
            ColumnDefinition(name="order_id", actual_name="oid", dtype="INTEGER", description="Order ID"),
            ColumnDefinition(name="user_id", actual_name="uid", dtype="INTEGER", description="User ID (FK)"),
            ColumnDefinition(name="amount", actual_name="order_amount", dtype="FLOAT", description="Order amount")
        ],
        primary_key="order_id"
    )
    relationship = RelationshipDefinition(
        name="user_orders",
        from_model="users",
        to_model="orders",
        from_columns=["user_id"],
        to_columns=["user_id"],
        type="ONE_TO_MANY"
    )
    return SemanticLayer(models=[users_model, orders_model], relationships=[relationship])

class TestLLMQueryService(unittest.TestCase):

    def setUp(self):
        self.sample_semantic_layer = create_sample_semantic_layer()
        # Basic settings with a dummy API key for tests not making actual calls
        self.settings_with_dummy_key = Settings(OPENAI_API_KEY="dummy_key_for_testing")
        self.settings_no_key = Settings(OPENAI_API_KEY=None) # type: ignore
        self.settings_placeholder_key = Settings(OPENAI_API_KEY="your_openai_api_key_here")


    def test_serialize_mdl_for_llm(self):
        serialized_output = serialize_mdl_for_llm(self.sample_semantic_layer)

        self.assertIn("Model: users (Actual Table: actual_users)", serialized_output)
        self.assertIn("Primary Key: user_id", serialized_output)
        self.assertIn("- Column: user_id (Actual Name in DB: id, Data Type: INTEGER)", serialized_output)
        self.assertIn("Description: User ID", serialized_output)
        self.assertIn("- Calculated Column: name_upper (Actual Name in DB: name_upper_calc, Data Type: TEXT, Expression: \"UPPER(name)\")", serialized_output)
        self.assertIn("Description: Uppercase user name", serialized_output)

        self.assertIn("Model: orders (Actual Table: actual_orders)", serialized_output)
        self.assertIn("- Column: amount (Actual Name in DB: order_amount, Data Type: FLOAT)", serialized_output)

        self.assertIn("Relationship: user_orders", serialized_output)
        self.assertIn("From Model: users (using columns: user_id)", serialized_output)
        self.assertIn("To Model: orders (using columns: user_id)", serialized_output)
        self.assertIn("Type: ONE_TO_MANY", serialized_output)

    @patch('zenbi.core.llm_service.ChatOpenAI') # Mock the ChatOpenAI class
    def test_generate_zensql_successful(self, MockChatOpenAI):
        # Configure the mock LLM instance and its invoke method
        mock_llm_instance = MagicMock()
        expected_llm_raw_output = (
            "/* ZENBI_CHART_SUGGESTION_START\n"
            "{\n"
            '  "chart_type": "bar",\n'
            '  "x_column": "name",\n'
            '  "y_columns": ["order_count"],\n'
            '  "title": "Order Count by User"\n'
            "}\n"
            "ZENBI_CHART_SUGGESTION_END */\n"
            "SELECT users.name, COUNT(orders.order_id) AS order_count FROM users JOIN orders ON users.user_id = orders.user_id GROUP BY users.name"
        )
        mock_llm_instance.invoke.return_value = expected_llm_raw_output

        # Make the MockChatOpenAI constructor return our mock_llm_instance
        MockChatOpenAI.return_value = mock_llm_instance

        service = LLMQueryService(settings=self.settings_with_dummy_key)

        user_nl_query = "Show me order counts per user, with a bar chart."
        actual_output = service.generate_zensql(self.sample_semantic_layer, user_nl_query)

        # Assert that the mock LLM's invoke method was called
        mock_llm_instance.invoke.assert_called_once()
        # Assert that ChatOpenAI was initialized with the correct parameters
        MockChatOpenAI.assert_called_with(
            openai_api_key=self.settings_with_dummy_key.OPENAI_API_KEY,
            model_name="gpt-3.5-turbo" # or whatever default is set
        )

        # Assert that the returned value from generate_zensql matches the mock's output
        self.assertEqual(actual_output, expected_llm_raw_output)

    def test_api_key_missing_error(self):
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY is not configured correctly"):
            LLMQueryService(settings=self.settings_no_key)

        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY is not configured correctly"):
            LLMQueryService(settings=self.settings_placeholder_key)

    @patch('zenbi.core.llm_service.ChatOpenAI')
    def test_generate_zensql_llm_error(self, MockChatOpenAI):
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.side_effect = Exception("LLM API Error")
        MockChatOpenAI.return_value = mock_llm_instance

        service = LLMQueryService(settings=self.settings_with_dummy_key)
        user_nl_query = "Any query"

        expected_error_output = "-- Error generating ZenSQL and chart suggestion: LLM API Error"
        actual_output = service.generate_zensql(self.sample_semantic_layer, user_nl_query)

        self.assertEqual(actual_output, expected_error_output)


if __name__ == '__main__':
    unittest.main()
