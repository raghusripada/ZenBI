from langchain_openai import ChatOpenAI
from langchain_community.chat_models.ollama import ChatOllama # Import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from zenbi.mdl.models import SemanticLayer, ModelDefinition, ColumnDefinition, CalculatedColumnDefinition, RelationshipDefinition
from zenbi.core.config import Settings
import logging # For logging information

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def serialize_mdl_for_llm(semantic_layer: SemanticLayer) -> str:
    # ... (existing serialize_mdl_for_llm function - no changes) ...
    output_lines = []
    output_lines.append("Models:")
    for model in semantic_layer.models:
        output_lines.append(f"  Model: {model.name} (Actual Table: {model.actual_table})")
        if model.description:
            output_lines.append(f"    Description: {model.description}")
        if model.primary_key:
            output_lines.append(f"    Primary Key: {model.primary_key} (Semantic name of the primary key column)")
        output_lines.append("    Columns:")
        for col in model.columns:
            col_type = "Column"
            expression_str = ""
            if isinstance(col, CalculatedColumnDefinition):
                col_type = "Calculated Column"
                expression_str = f", Expression: \"{col.expression}\""
            output_lines.append(f"      - {col_type}: {col.name} (Actual Name in DB: {col.actual_name}, Data Type: {col.dtype}{expression_str})")
            if col.description:
                output_lines.append(f"        Description: {col.description}")
            if col.properties:
                output_lines.append(f"        Properties: {col.properties}")
    if semantic_layer.relationships:
        output_lines.append("\nRelationships:")
        for rel in semantic_layer.relationships:
            output_lines.append(f"  Relationship: {rel.name}")
            output_lines.append(f"    Type: {rel.type}")
            output_lines.append(f"    From Model: {rel.from_model} (using columns: {', '.join(rel.from_columns)})")
            output_lines.append(f"    To Model: {rel.to_model} (using columns: {', '.join(rel.to_columns)})")
    else:
        output_lines.append("\nNo relationships defined.")
    return "\n".join(output_lines)


class LLMQueryService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = None # Initialize llm attribute

        provider = self.settings.LLM_PROVIDER.lower()
        logger.info(f"Initializing LLM service with provider: {provider}")

        if provider == "ollama":
            if not self.settings.OLLAMA_BASE_URL:
                raise ValueError("OLLAMA_BASE_URL must be configured when LLM_PROVIDER is 'ollama'.")
            try:
                self.llm = ChatOllama(
                    model=self.settings.OLLAMA_MODEL_ZENSQL, # Using ZenSQL model for the main LLM instance
                    base_url=str(self.settings.OLLAMA_BASE_URL), # Convert HttpUrl to string
                    temperature=0 # For more deterministic output
                )
                # Note: For chart suggestions, if OLLAMA_MODEL_CHART is different,
                # a separate instance or logic to switch model per call might be needed.
                # For now, the same LLM instance is used for the combined prompt.
                logger.info(f"Using Ollama LLM service. ZenSQL/Chart Model: {self.settings.OLLAMA_MODEL_ZENSQL}, URL: {self.settings.OLLAMA_BASE_URL}")
            except Exception as e:
                logger.error(f"Failed to initialize Ollama client: {e}")
                raise ValueError(f"Ollama client initialization failed: {e}") from e

        elif provider == "openai":
            if not self.settings.OPENAI_API_KEY or self.settings.OPENAI_API_KEY == "your_openai_api_key_here":
                raise ValueError("OPENAI_API_KEY is not configured correctly for 'openai' provider.")
            try:
                self.llm = ChatOpenAI(
                    openai_api_key=self.settings.OPENAI_API_KEY,
                    model_name=self.settings.OPENAI_MODEL_NAME, # Using the configured OpenAI model
                    temperature=0 # For more deterministic output
                )
                logger.info(f"Using OpenAI LLM service. Model: {self.settings.OPENAI_MODEL_NAME}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise ValueError(f"OpenAI client initialization failed: {e}") from e
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: '{self.settings.LLM_PROVIDER}'. Choose 'openai' or 'ollama'.")

    def generate_zensql(self, semantic_layer: SemanticLayer, user_query: str) -> str:
        """
        Generates ZenSQL and optionally a chart suggestion using the configured LLM.
        Returns a raw string that may contain both the SQL and the chart suggestion block.
        """
        if self.llm is None: # Should not happen if __init__ succeeded
            raise RuntimeError("LLM client is not initialized.")

        mdl_context = serialize_mdl_for_llm(semantic_layer)

        prompt_template_str = """
You are an expert SQL writer and data visualization assistant.
Based on the following semantic model context, write a SQL query that answers the user's question.
Use the semantic names (not actual database names) for tables and columns provided in the context.
The SQL query should be valid for a typical SQL database.

Semantic Model Context:
---
{mdl_context}
---

User Question: {user_question}

Instructions for Output:
1.  If the user's question is suitable for visualization, include a chart suggestion.
    The chart suggestion MUST be a JSON object within a comment block formatted EXACTLY as follows:
    /* ZENBI_CHART_SUGGESTION_START
    {{
      "chart_type": "bar | line | pie | table | null",
      "x_column": "semantic_column_name_for_x_axis_or_labels",
      "y_columns": ["semantic_column_name_for_y_axis_or_values"],
      "title": "Suggested Chart Title"
    }}
    ZENBI_CHART_SUGGESTION_END */
    - "chart_type" can be "bar", "line", "pie". Use "table" if the data is best presented as a table, or "null" if no specific chart is suitable.
    - "x_column" should be the semantic name of a column from the SELECT statement that will be used for the X-axis in bar/line charts, or labels in pie charts.
    - "y_columns" should be a list containing one or more semantic names of columns from the SELECT statement for the Y-axis or values.
    - If a chart is suggested, ensure the SQL query selects the necessary columns (x_column, y_columns) with their semantic names as aliases if they are calculated or aggregated.
    - If suggesting a chart, make sure the SQL query produces data appropriate for that chart (e.g., aggregations for bar/pie charts).

2.  After the optional chart suggestion block (if any), output the SQL query.
    The SQL query MUST start immediately after the chart suggestion block's closing comment (ZENBI_CHART_SUGGESTION_END */) or at the beginning of your response if no chart is suggested.
    Do NOT include any other text or explanations before or after the SQL query, other than the specified chart suggestion block.

Example of a response WITH a chart suggestion:
/* ZENBI_CHART_SUGGESTION_START
{{
  "chart_type": "bar",
  "x_column": "user_city",
  "y_columns": ["number_of_users"],
  "title": "User Count by City"
}}
ZENBI_CHART_SUGGESTION_END */
SELECT city AS user_city, COUNT(user_id) AS number_of_users FROM users GROUP BY city

Example of a response WITHOUT a chart suggestion (e.g., for a query like "list all users"):
SELECT user_id, email, name, city FROM users

Final SQL Query:
"""
        prompt_template = ChatPromptTemplate.from_template(prompt_template_str)

        # The chain uses the initialized self.llm (either ChatOpenAI or ChatOllama)
        chain = prompt_template | self.llm | StrOutputParser()

        try:
            raw_output = chain.invoke({
                "mdl_context": mdl_context,
                "user_question": user_query
            })
            return raw_output
        except Exception as e:
            logger.error(f"Error during LLM invoke call with provider {self.settings.LLM_PROVIDER}: {e}")
            # Return a formatted error string that can be picked up by parsing logic if needed
            return f"-- Error generating ZenSQL and chart suggestion: LLM call failed with {self.settings.LLM_PROVIDER}. Details: {e}"
