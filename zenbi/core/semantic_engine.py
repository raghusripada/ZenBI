import sqlglot
import sqlglot.expressions as exp
from zenbi.mdl.models import (
    SemanticLayer,
    ModelDefinition,
    ColumnDefinition,
    CalculatedColumnDefinition,
    RelationshipDefinition # Added for completeness, though not directly used in __init__
)
from typing import Union, Dict, cast

class SemanticEngine:
    def __init__(self, semantic_layer: SemanticLayer, target_dialect: str = "sqlite"):
        self.semantic_layer = semantic_layer
        self.target_dialect = target_dialect
        self.models_map: Dict[str, ModelDefinition] = {}
        self.columns_map: Dict[str, Dict[str, Union[ColumnDefinition, CalculatedColumnDefinition]]] = {}
        # It might be redundant to have a separate calculated_columns_map if columns_map holds both
        # self.calculated_columns_map: Dict[str, Dict[str, CalculatedColumnDefinition]] = {}

        self._preprocess_semantic_layer()

    def _preprocess_semantic_layer(self):
        """
        Populates internal lookup maps from the semantic layer.
        """
        for model in self.semantic_layer.models:
            self.models_map[model.name] = model
            self.columns_map[model.name] = {}
            # self.calculated_columns_map[model.name] = {}
            for column in model.columns:
                self.columns_map[model.name][column.name] = column
                # if isinstance(column, CalculatedColumnDefinition):
                #     self.calculated_columns_map[model.name][column.name] = column

    def _resolve_column_semantic_info(self, column_node: exp.Column, current_scope_models: Dict[str, str]):
        """
        Tries to find the semantic model and column definition for a given column node.
        `current_scope_models` is a map of alias_or_name -> semantic_model_name for tables in the current query scope.
        Returns (semantic_model_name, column_definition) or (None, None).
        """
        col_name = column_node.name
        table_alias_or_name = column_node.table # This could be an alias or a semantic model name

        semantic_model_name = None
        if table_alias_or_name:
            semantic_model_name = current_scope_models.get(table_alias_or_name)
        elif len(current_scope_models) == 1: # Unqualified column, only one table in scope
            semantic_model_name = list(current_scope_models.values())[0]

        if semantic_model_name:
            model_cols = self.columns_map.get(semantic_model_name)
            if model_cols and col_name in model_cols:
                return semantic_model_name, model_cols[col_name]

        # Fallback: If not found with alias, and it's a direct semantic model name (no alias used)
        if not semantic_model_name and table_alias_or_name in self.models_map:
            semantic_model_name = table_alias_or_name
            model_cols = self.columns_map.get(semantic_model_name)
            if model_cols and col_name in model_cols:
                 return semantic_model_name, model_cols[col_name]

        # If still not found, it might be a column from a CTE or a complex subquery not directly in models_map
        return None, None


    def _transform_node(self, node: exp.Expression, current_scope_models: Dict[str, str]):
        """
        Recursively transforms nodes of the SQL AST from semantic names to actual names.
        `current_scope_models` maps table aliases (or semantic names if no alias) in the current
        query part to their semantic model names.
        """

        # Step 1: Update current_scope_models for FROM and JOIN clauses
        # This needs to be done before transforming children in these clauses
        if isinstance(node, (exp.From, exp.Join)):
            if isinstance(node.this, exp.Table):
                table_node = node.this
                semantic_model_name = table_node.name
                if semantic_model_name in self.models_map:
                    # If there's an alias, map alias to semantic_model_name. Otherwise, map semantic_model_name to itself.
                    alias_or_name = table_node.alias_or_name
                    current_scope_models[alias_or_name] = semantic_model_name


        # Transform children first (depth-first traversal)
        # This ensures that by the time we process a node, its children are already transformed if necessary.
        # However, for tables and columns, we need to handle them before their children (e.g. table name before columns within it).
        # SQLGlot's transform usually handles this by applying pre, node, post visitors.
        # Here, we are doing a manual traversal.

        # Table transformation
        if isinstance(node, exp.Table):
            semantic_model_name = node.name # This is the semantic name used in ZenSQL
            if semantic_model_name in self.models_map:
                actual_table_name = self.models_map[semantic_model_name].actual_table
                node.set('this', exp.to_identifier(actual_table_name))
                # Update current_scope_models: if there's an alias, map alias to semantic_model_name.
                # Otherwise, map new actual_table_name to semantic_model_name (or old semantic_model_name to itself).
                # This part is tricky because node.alias_or_name is used.
                alias = node.alias
                key_for_scope = alias if alias else semantic_model_name # semantic_model_name was the original key

                # If an alias exists, current_scope_models should map this alias to the semantic_model_name
                # If no alias, the semantic_model_name itself is the key
                current_scope_models[node.alias_or_name] = semantic_model_name
            return node

        # Column transformation
        if isinstance(node, exp.Column):
            semantic_model_name, column_def = self._resolve_column_semantic_info(node, current_scope_models)

            if column_def:
                if isinstance(column_def, CalculatedColumnDefinition):
                    # Parse the expression of the calculated column
                    # The expression uses semantic names relative to its own model
                    calc_expr_ast = sqlglot.parse_one(column_def.expression, read=sqlglot.dialects.Dialects.SQLGLOT)

                    # We need to transform this sub-AST.
                    # The context for this transformation is the model the calc column belongs to.
                    calc_col_model_scope = {column_def.name: semantic_model_name} # Simplified scope for this sub-expression

                    # More accurately, the scope for the calculated column's expression
                    # should be the model it belongs to. Any unqualified columns in its expression
                    # refer to other columns *within that same model*.
                    # Qualified columns (e.g. other_model.col) should be resolved based on relationships (future).
                    # For now, assume expressions only refer to columns within the same model.

                    # Create a new scope for transforming the calculated column's expression
                    # This scope maps the semantic name of the model to itself, as columns in the expression
                    # are expected to be qualified by this model's semantic name or be unqualified (implicitly this model).
                    expression_scope_models = {semantic_model_name: semantic_model_name}

                    transformed_calc_expr_ast = calc_expr_ast.transform(
                        self._transform_node, current_scope_models=expression_scope_models, copy=True # Use copy=True to avoid modifying the original parsed expression
                    )

                    # Replace the original column node with the transformed expression, aliased
                    # Use column_def.name as the alias because LLM is expected to use semantic name for alias
                    return exp.Alias(this=transformed_calc_expr_ast, alias=exp.to_identifier(column_def.name))
                else: # It's a direct ColumnDefinition
                    node.set('this', exp.to_identifier(column_def.actual_name))
            # If column_def is None, it means it's not a semantic column we know about (e.g. from a CTE, or an already transformed one).
            # Or it's a function call like COUNT(*), which sqlglot parses as a Column with name '*'.
            # We should not modify it in that case.
            return node

        return node


    def transpile_zensql_to_sql(self, zensql_query: str) -> str:
        try:
            # Using SQLGLOT as the read dialect assumes ZenSQL is already somewhat SQL-like,
            # which is true as per LLM instructions.
            parsed_ast = sqlglot.parse_one(zensql_query, read=sqlglot.dialects.Dialects.SQLGLOT)
        except sqlglot.errors.ParseError as e:
            raise ValueError(f"Error parsing ZenSQL query: {e}") from e

        # current_scope_models will map alias_or_original_name -> semantic_model_name
        # This needs to be built up as we traverse FROM/JOIN clauses.
        # For the transform method, this state needs to be passed along.
        # sqlglot's transform method can take a `**kwargs` which are passed to the callback.

        # Initial scope building:
        # We need to identify all tables and their aliases from the AST first to build an initial scope.
        # This is because a column in SELECT might appear before its table is defined in FROM.
        initial_scope_models: Dict[str, str] = {}
        for table_exp in parsed_ast.find_all(exp.Table):
            semantic_model_name = table_exp.name
            if semantic_model_name in self.models_map:
                 # Map alias to semantic name if alias exists, otherwise map semantic name to itself
                initial_scope_models[table_exp.alias_or_name] = semantic_model_name

        # If there's only one table and no alias, its columns might be unqualified.
        # Ensure the semantic model name itself is in the scope if no aliases are used for it.
        if len(initial_scope_models) == 1:
            single_alias = list(initial_scope_models.keys())[0]
            single_semantic_name = initial_scope_models[single_alias]
            if single_alias == single_semantic_name: # No alias, semantic name used directly
                 initial_scope_models[single_semantic_name] = single_semantic_name


        transformed_ast = parsed_ast.transform(self._transform_node, current_scope_models=initial_scope_models, copy=True)

        if transformed_ast is None:
            raise ValueError("Transformation resulted in an empty AST.")

        return transformed_ast.sql(dialect=self.target_dialect, pretty=True)

# Example Usage (for testing purposes, will be in tests later)
if __name__ == '__main__':
    # Manual setup of a sample SemanticLayer for local testing
    sample_mdl_data = {
        "models": [
            {
                "name": "users", "actual_table": "raw_users_table",
                "columns": [
                    {"name": "user_id", "actual_name": "id", "dtype": "INTEGER"},
                    {"name": "email", "actual_name": "email_addr", "dtype": "TEXT"},
                    {"name": "age", "actual_name": "user_age", "dtype": "INTEGER"}
                ]
            },
            {
                "name": "orders", "actual_table": "all_orders",
                "columns": [
                    {"name": "order_id", "actual_name": "oid", "dtype": "INTEGER"},
                    {"name": "user_id", "actual_name": "uid", "dtype": "INTEGER"}, # FK
                    {"name": "amount", "actual_name": "order_amount", "dtype": "FLOAT"},
                    {
                        "name": "amount_plus_tax", "actual_name": "calc_amount_tax", # actual_name for calc field might not be used if alias is preferred
                        "dtype": "FLOAT", "expression": "amount * 1.1", # uses 'amount' (semantic name from same model)
                        "is_calculated": True # Custom flag to help Pydantic differentiate if not using Union types
                    }
                ]
            }
        ],
        "relationships": [
            {
                "name": "user_to_orders", "from_model": "users", "to_model": "orders",
                "from_columns": ["user_id"], "to_columns": ["user_id"], "type": "ONE_TO_MANY"
            }
        ]
    }
    # Hacky way to make CalculatedColumnDefinition work without separate Pydantic model for this test
    for model_data in sample_mdl_data["models"]:
        new_columns = []
        for col_data in model_data["columns"]:
            if col_data.pop("is_calculated", False):
                new_columns.append(CalculatedColumnDefinition(**col_data))
            else:
                new_columns.append(ColumnDefinition(**col_data))
        model_data["columns"] = new_columns

    semantic_layer_instance = SemanticLayer(**sample_mdl_data)
    engine = SemanticEngine(semantic_layer_instance, target_dialect="duckdb")

    # Test cases
    test_zensql_1 = "SELECT user_id, email FROM users"
    # Expected: SELECT id, email_addr FROM raw_users_table

    test_zensql_2 = "SELECT u.email, u.age FROM users u WHERE u.age > 20"
    # Expected: SELECT u.email_addr, u.user_age FROM raw_users_table AS u WHERE u.user_age > 20

    test_zensql_3 = "SELECT order_id, amount, amount_plus_tax FROM orders"
    # Expected: SELECT o.oid, o.order_amount, o.order_amount * 1.1 AS amount_plus_tax FROM all_orders AS o
    # Or without alias for table if not used: SELECT oid, order_amount, order_amount * 1.1 AS amount_plus_tax FROM all_orders

    test_zensql_4 = "SELECT users.email, orders.amount FROM users JOIN orders ON users.user_id = orders.user_id"
    # Expected: SELECT raw_users_table.email_addr, all_orders.order_amount FROM raw_users_table JOIN all_orders ON raw_users_table.id = all_orders.uid

    print(f"--- Test Case 1: Simple Select ---")
    print(f"ZenSQL: {test_zensql_1}")
    print(f"Transpiled SQL: {engine.transpile_zensql_to_sql(test_zensql_1)}\n")

    print(f"--- Test Case 2: Select with Alias ---")
    print(f"ZenSQL: {test_zensql_2}")
    print(f"Transpiled SQL: {engine.transpile_zensql_to_sql(test_zensql_2)}\n")

    print(f"--- Test Case 3: Select with Calculated Field ---")
    print(f"ZenSQL: {test_zensql_3}")
    print(f"Transpiled SQL: {engine.transpile_zensql_to_sql(test_zensql_3)}\n")

    print(f"--- Test Case 4: Select with Join ---")
    print(f"ZenSQL: {test_zensql_4}")
    print(f"Transpiled SQL: {engine.transpile_zensql_to_sql(test_zensql_4)}\n")
