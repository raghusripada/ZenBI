from langchain_openai import ChatOpenAI
from langchain_community.chat_models.ollama import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from zenbi.mdl.models import SemanticLayer, ModelDefinition, ColumnDefinition, CalculatedColumnDefinition, RelationshipDefinition
from zenbi.core.config import Settings
import logging
import json

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
        self.llm = None  # For ZenSQL and Chart suggestions
        self.insight_llm = None # For Textual Insights

        provider = self.settings.LLM_PROVIDER.lower()
        logger.info(f"Initializing LLM service with provider: {provider}")

        if provider == "ollama":
            if not self.settings.OLLAMA_BASE_URL:
                raise ValueError("OLLAMA_BASE_URL must be configured when LLM_PROVIDER is 'ollama'.")
            try:
                base_url_str = str(self.settings.OLLAMA_BASE_URL)
                self.llm = ChatOllama(
                    model=self.settings.OLLAMA_MODEL_ZENSQL,
                    base_url=base_url_str,
                    temperature=0
                )
                logger.info(f"Using Ollama LLM service for ZenSQL/Charts. Model: {self.settings.OLLAMA_MODEL_ZENSQL}, URL: {base_url_str}")

                if self.settings.OLLAMA_MODEL_INSIGHTS == self.settings.OLLAMA_MODEL_ZENSQL:
                    self.insight_llm = self.llm
                    logger.info(f"Reusing Ollama model for Insights: {self.settings.OLLAMA_MODEL_INSIGHTS}")
                else:
                    self.insight_llm = ChatOllama(
                        model=self.settings.OLLAMA_MODEL_INSIGHTS,
                        base_url=base_url_str,
                        temperature=0.1 # Slightly higher temp for insights might be desirable
                    )
                    logger.info(f"Using separate Ollama model for Insights: {self.settings.OLLAMA_MODEL_INSIGHTS}, URL: {base_url_str}")

            except Exception as e:
                logger.error(f"Failed to initialize Ollama client(s): {e}")
                raise ValueError(f"Ollama client initialization failed: {e}") from e

        elif provider == "openai":
            if not self.settings.OPENAI_API_KEY or self.settings.OPENAI_API_KEY == "your_openai_api_key_here":
                raise ValueError("OPENAI_API_KEY is not configured correctly for 'openai' provider.")
            try:
                self.llm = ChatOpenAI(
                    openai_api_key=self.settings.OPENAI_API_KEY,
                    model_name=self.settings.OPENAI_MODEL_NAME,
                    temperature=0
                )
                logger.info(f"Using OpenAI LLM service for ZenSQL/Charts. Model: {self.settings.OPENAI_MODEL_NAME}")

                if self.settings.OPENAI_MODEL_INSIGHTS == self.settings.OPENAI_MODEL_NAME:
                    self.insight_llm = self.llm
                    logger.info(f"Reusing OpenAI model for Insights: {self.settings.OPENAI_MODEL_INSIGHTS}")
                else:
                    self.insight_llm = ChatOpenAI(
                        openai_api_key=self.settings.OPENAI_API_KEY,
                        model_name=self.settings.OPENAI_MODEL_INSIGHTS,
                        temperature=0.1 # Slightly higher temp for insights
                    )
                    logger.info(f"Using separate OpenAI model for Insights: {self.settings.OPENAI_MODEL_INSIGHTS}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client(s): {e}")
                raise ValueError(f"OpenAI client initialization failed: {e}") from e
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: '{self.settings.LLM_PROVIDER}'. Choose 'openai' or 'ollama'.")

    def generate_zensql(self, semantic_layer: SemanticLayer, user_query: str) -> str:
        if self.llm is None:
            raise RuntimeError("Primary LLM client (for ZenSQL/Charts) is not initialized.")
        # ... (rest of generate_zensql method remains the same, using self.llm) ...
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
        chain = prompt_template | self.llm | StrOutputParser()
        try:
            raw_output = chain.invoke({
                "mdl_context": mdl_context,
                "user_question": user_query
            })
            return raw_output
        except Exception as e:
            logger.error(f"Error during LLM invoke call with provider {self.settings.LLM_PROVIDER} for ZenSQL: {e}")
            return f"-- Error generating ZenSQL and chart suggestion: LLM call failed with {self.settings.LLM_PROVIDER}. Details: {e}"


    def _format_results_for_llm(self, results: list[dict], max_rows: int = 10, max_cols: int = 10, max_chars_per_cell: int = 50) -> str:
        if not results:
            return "No results found for the query."

        num_original_rows = len(results)

        # Determine headers from the first row, up to max_cols
        if num_original_rows > 0:
            original_headers = list(results[0].keys())
            headers = original_headers[:max_cols]
        else: # Should have been caught by `if not results` but defensive
            return "Results found, but no column headers detected (empty data structure)."

        if not headers:
            return "Results found, but no column headers detected."

        # Truncate rows
        truncated_rows_data = results[:max_rows]

        # Format as Markdown table
        md_table_parts = []
        md_table_parts.append("| " + " | ".join(headers) + " |")
        md_table_parts.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for row in truncated_rows_data:
            row_values = []
            for header in headers:
                cell_value = str(row.get(header, '')) # Get value, default to empty string
                if len(cell_value) > max_chars_per_cell:
                    cell_value = cell_value[:max_chars_per_cell - 3] + "..."
                row_values.append(cell_value)
            md_table_parts.append("| " + " | ".join(row_values) + " |")

        md_table = "\n".join(md_table_parts)

        truncation_notes = []
        if num_original_rows > max_rows:
            truncation_notes.append(f"Showing first {max_rows} of {num_original_rows} total rows.")
        if len(original_headers) > max_cols:
            truncation_notes.append(f"Showing first {max_cols} of {len(original_headers)} total columns.")

        if truncation_notes:
            md_table += "\n\nNote: " + " ".join(truncation_notes)

        return md_table.strip()

    def generate_textual_insight(self, natural_language_query: str, final_sql_query: str, query_results: list[dict]) -> str:
        if self.insight_llm is None: # Check if the insight LLM client is initialized
            logger.warning("Insight LLM client is not initialized. Skipping textual insight generation.")
            return "Textual insight generation is currently unavailable."

        formatted_results = self._format_results_for_llm(query_results)

        prompt_template_str = """
You are an expert data analyst. Your task is to provide a concise textual summary and insight based on the provided data, which was generated in response to a user's question.

User's Original Question:
"{natural_language_query}"

Executed SQL Query Used to Fetch Data:
"{final_sql_query}"

Query Results Data:
---
{formatted_query_results}
---

Please adhere to the following guidelines for your response:
1. Directly answer the user's original question if the provided data allows for a clear answer.
2. Provide a brief summary of the key findings or significant trends present in the data.
3. Keep your entire insight concise and to the point, ideally 1-3 sentences.
4. If the data is empty (e.g., "No results found for the query."), explicitly state that "No results were found" or "The query returned no data."
5. If the data is present but does not seem to directly answer the question or offer significant insights, you can state something like "The data shows [brief description of data], but it does not directly answer the question about [topic of question]."
6. Do NOT repeat the SQL query in your summary.
7. Do NOT reproduce the raw data table in your summary.
8. Your output should be only the textual insight, with no additional conversational fluff or lead-in phrases like "Here's an insight:".

Textual Insight:
"""

        prompt_template = ChatPromptTemplate.from_template(prompt_template_str)
        insight_chain = prompt_template | self.insight_llm | StrOutputParser()

        try:
            insight = insight_chain.invoke({
                "natural_language_query": natural_language_query,
                "final_sql_query": final_sql_query,
                "formatted_query_results": formatted_results
            })
            return insight.strip()
        except Exception as e:
            logger.error(f"Error during LLM call for textual insight with provider {self.settings.LLM_PROVIDER}: {e}")
            return "Error generating textual insight."
