import unittest
from unittest.mock import patch, MagicMock
from zenbi.core.llm_service import LLMQueryService, serialize_mdl_for_llm
from zenbi.core.config import Settings
from zenbi.mdl.models import SemanticLayer, ModelDefinition, ColumnDefinition, CalculatedColumnDefinition, RelationshipDefinition
from typing import List

# Helper to create a sample SemanticLayer for testing
def create_sample_semantic_layer() -> SemanticLayer:
    # ... (same helper function as before) ...
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

        # OpenAI specific settings
        self.settings_openai_valid = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY="fake_openai_key", OPENAI_MODEL_NAME="gpt-test")
        self.settings_openai_no_key = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY=None) # type: ignore
        self.settings_openai_placeholder_key = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY="your_openai_api_key_here")

        # Ollama specific settings
        self.settings_ollama_valid = Settings(LLM_PROVIDER="ollama", OLLAMA_BASE_URL="http://localhost:11434", OLLAMA_MODEL_ZENSQL="ollama-test-model")
        self.settings_ollama_no_url = Settings(LLM_PROVIDER="ollama", OLLAMA_BASE_URL=None) # type: ignore

        self.expected_llm_raw_output = (
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

    def test_serialize_mdl_for_llm(self):
        # ... (same test as before, no changes needed) ...
        serialized_output = serialize_mdl_for_llm(self.sample_semantic_layer)
        self.assertIn("Model: users (Actual Table: actual_users)", serialized_output)
        self.assertIn("- Calculated Column: name_upper (Actual Name in DB: name_upper_calc, Data Type: TEXT, Expression: \"UPPER(name)\")", serialized_output)
        self.assertIn("Relationship: user_orders", serialized_output)


    # --- OpenAI Provider Tests ---
    @patch('zenbi.core.llm_service.ChatOpenAI')
    def test_openai_initialization_successful(self, MockChatOpenAI):
        mock_llm_instance = MagicMock()
        MockChatOpenAI.return_value = mock_llm_instance

        service = LLMQueryService(settings=self.settings_openai_valid)
        self.assertIsNotNone(service.llm)
        MockChatOpenAI.assert_called_with(
            openai_api_key=self.settings_openai_valid.OPENAI_API_KEY,
            model_name=self.settings_openai_valid.OPENAI_MODEL_NAME,
            temperature=0
        )

    def test_openai_api_key_missing_error(self):
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY is not configured correctly"):
            LLMQueryService(settings=self.settings_openai_no_key)
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY is not configured correctly"):
            LLMQueryService(settings=self.settings_openai_placeholder_key)

    @patch('zenbi.core.llm_service.ChatOpenAI')
    def test_generate_zensql_with_openai_provider(self, MockChatOpenAI):
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = self.expected_llm_raw_output
        MockChatOpenAI.return_value = mock_llm_instance

        service = LLMQueryService(settings=self.settings_openai_valid)
        user_nl_query = "Show order counts per user."
        actual_output = service.generate_zensql(self.sample_semantic_layer, user_nl_query)

        mock_llm_instance.invoke.assert_called_once()
        self.assertEqual(actual_output, self.expected_llm_raw_output)

    # --- Ollama Provider Tests ---
    @patch('zenbi.core.llm_service.ChatOllama')
    def test_ollama_initialization_successful(self, MockChatOllama):
        mock_llm_instance = MagicMock()
        MockChatOllama.return_value = mock_llm_instance

        service = LLMQueryService(settings=self.settings_ollama_valid)
        self.assertIsNotNone(service.llm)
        MockChatOllama.assert_called_with(
            model=self.settings_ollama_valid.OLLAMA_MODEL_ZENSQL,
            base_url=str(self.settings_ollama_valid.OLLAMA_BASE_URL),
            temperature=0
        )

    def test_ollama_initialization_missing_url_error(self):
        with self.assertRaisesRegex(ValueError, "OLLAMA_BASE_URL must be configured"):
            LLMQueryService(settings=self.settings_ollama_no_url)

    @patch('zenbi.core.llm_service.ChatOllama')
    def test_generate_zensql_with_ollama_provider(self, MockChatOllama):
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = self.expected_llm_raw_output
        MockChatOllama.return_value = mock_llm_instance

        service = LLMQueryService(settings=self.settings_ollama_valid)
        user_nl_query = "Show order counts per user with Ollama."
        actual_output = service.generate_zensql(self.sample_semantic_layer, user_nl_query)

        mock_llm_instance.invoke.assert_called_once()
        self.assertEqual(actual_output, self.expected_llm_raw_output)

    # --- General Error Handling Tests ---
    def test_unsupported_llm_provider_error(self):
        settings_invalid_provider = Settings(LLM_PROVIDER="unsupported_provider")
        with self.assertRaisesRegex(ValueError, "Unsupported LLM_PROVIDER: 'unsupported_provider'"):
            LLMQueryService(settings=settings_invalid_provider)

    @patch('zenbi.core.llm_service.ChatOpenAI') # Test with OpenAI, but logic is provider-agnostic
    def test_generate_zensql_llm_invoke_error(self, MockChatOpenAI):
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.side_effect = Exception("LLM API Error")
        MockChatOpenAI.return_value = mock_llm_instance

        service = LLMQueryService(settings=self.settings_openai_valid)
        user_nl_query = "Any query"

        expected_error_output = f"-- Error generating ZenSQL and chart suggestion: LLM call failed with {self.settings_openai_valid.LLM_PROVIDER}. Details: LLM API Error"
        actual_output = service.generate_zensql(self.sample_semantic_layer, user_nl_query)

        self.assertEqual(actual_output, expected_error_output)

if __name__ == '__main__':
    unittest.main()
