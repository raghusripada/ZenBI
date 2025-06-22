# ZenBI Future Enhancements Roadmap

This document outlines potential future enhancements and a ToDo list to build ZenBI into a more comprehensive and user-friendly natural language powered BI tool with a robust semantic layer.

**Note on OpenMetadata Integration:**
The OpenMetadata integration features (including bootstrapping MDL from an OpenMetadata instance and other planned broader integrations) are temporarily deferred. This is due to current dependency incompatibilities between the `openmetadata-ingestion` package (which primarily supports Pydantic V1 and SQLAlchemy V1.x) and ZenBI's core dependencies like Langchain, Pydantic V2, and SQLAlchemy V2.x.

We plan to revisit and re-integrate OpenMetadata functionality once its client libraries offer stable, long-term support for Pydantic V2 and SQLAlchemy V2.x, or when a more robust solution for managing these transitive dependency conflicts can be implemented for ZenBI. The items related to OpenMetadata below remain part of the long-term vision.

## I. Semantic Layer Engine Enhancements (ZenBI Core)

### MDL - Advanced Calculated Fields & Metrics
- [ ] **Support for Complex Expressions:** Ensure the `SemanticEngine` and MDL can handle more complex SQL functions and expressions within calculated field definitions (e.g., window functions, CASE statements, date arithmetic, string manipulations).
- [ ] **Calculated Fields Referencing Other Calculated Fields:** Robustly support and test scenarios where one calculated field uses another from the same model in its expression.
- [ ] **Contextual Aggregations in Calculated Fields:** Allow calculated fields to define aggregations that are aware of the query context (e.g., a metric that calculates `SUM(sales)` but can be sliced by dimensions not explicitly in its base definition).

### MDL - Macros/Reusable Functions
- [ ] **Design Macro System:** Define a syntax within the MDL (e.g., YAML/JSON compatible) for creating reusable, parameterized expressions or SQL snippets.
- [ ] **Implement Macro Expansion:** Update the `SemanticEngine`'s transpilation process to correctly expand these macros with provided arguments before final SQL generation.

### MDL - Advanced Relationships & Join Logic
- [ ] **Proactive Join Inference:** Enhance `SemanticEngine` to (optionally) infer and add necessary JOINs based on relationships defined in the MDL, even if the ZenSQL from the LLM is less explicit about joins.
- [ ] **Support for Complex Join Conditions:** Ensure the MDL and engine can handle multi-column joins and potentially more complex join expressions.
- [ ] **Relationship Cardinality Hints:** Allow MDL to specify cardinality (1:1, 1:N, N:M) and potentially use this information to optimize LLM prompt context or join strategies.

### MDL - Enhanced Type System & Casting
- [ ] **Richer MDL Data Types:** Expand the set of supported data types in the MDL to better match common database types and allow for more precise semantic definitions.
- [ ] **Automatic Type Casting Logic:** Improve the `SemanticEngine`'s ability to handle and insert appropriate SQL `CAST` operations during transpilation.

### Query Optimization
- [ ] **Integrate SQLGlot Optimizer:** Leverage `sqlglot`'s optimizer capabilities more fully to standardize or improve the ZenSQL AST before or after transformation.

### Multi-Dialect Robustness
- [ ] **Extended Dialect Testing:** Systematically test transpilation and execution against a wider range of SQL dialects supported by SQLGlot and SQLAlchemy.

## II. Application Layer Enhancements (ZenBI API & Services)

### AI-Generated Textual Insights (Advanced)
- [ ] **Configurable Insight Granularity:** Allow users to request different levels of detail for insights (e.g., brief summary vs. detailed analysis).
- [ ] **Trend Analysis & Anomaly Detection:** Task the LLM with identifying trends, patterns, or anomalies in the result set and reporting them.
- [ ] **Comparative Insights:** If a query involves comparisons, the LLM should generate insights reflecting that comparison.

### "Why" Explanations / Drill-Down Paths
- [ ] **Explain Query Results:** After a query, allow users to ask "why" a certain result occurred. The system could try to find contributing factors by generating follow-up queries.

### Data Governance & Access Control
- [ ] **User Roles & Permissions Model:** Define a basic role-based access control system.
- [ ] **MDL-Level Access Rules:** Allow defining which semantic models or columns are accessible to which roles.
- [ ] **Enforce Access in Engine/API:** The `SemanticEngine` or API layer would need to filter or error out if a user tries to query restricted semantic entities.

### Caching
- [ ] **Query Result Caching:** Implement caching for frequently executed queries/MDL configurations.
- [ ] **MDL Cache:** Cache parsed MDL objects.

## III. User Interface & User Experience (ZenBI Frontend & MDL Definition)

### No-Code/Low-Code MDL Management
-   **LLM-Assisted MDL Generation/Refinement:**
    - [ ] **Column Property Modification via NL:** Allow users to change column descriptions, display names via natural language. (This is the next planned feature from previous discussions).
    - [ ] **Calculated Field Creation via NL:** e.g., "Create a metric 'Revenue per User' as 'sum(total_revenue) / count(distinct user_id)'."
    - [ ] **Relationship Definition via NL:** e.g., "Link the 'users' table to the 'orders' table using 'user_id'."
    - [ ] **Model Discovery/Bootstrapping via NL:** e.g., "Analyze my 'sales_data' table and suggest a basic semantic model." (Could also leverage OpenMetadata).
-   **GUI-Based Semantic Modeler (Longer Term):**
    - [ ] Design and implement a web UI for visually creating and editing ZenBI MDLs.
    - [ ] Features: Drag-and-drop, form-based property editing, visual relationship linking, formula builder UI.
    - [ ] UI would generate/update the underlying MDL YAML/JSON files.

### Advanced Charting & Visualization
- [ ] **User-Driven Chart Configuration:** Allow users to select chart types, axes, and aggregations directly in the UI from query results.
- [ ] **Support for More Chart Types:** Integrate more complex chart types (scatter plots, heatmaps, combination charts).
- [ ] **Chart Persistence/Saving:** Allow users to save chart configurations.

### Dashboarding
- [ ] **Basic Dashboarding UI:** Allow users to combine multiple saved queries/charts onto a single dashboard view.
- [ ] **Dashboard Layout Customization.**

### Query History & Saved Queries
- [ ] Store user query history.
- [ ] Allow users to save, name, and re-run frequently used queries.

### Enhanced NLQ Input
- [ ] Autocomplete/suggestions for semantic terms as users type their query.
- [ ] Disambiguation prompts if a natural language query is unclear.

### Application Polish
- [ ] User accounts and authentication.
- [ ] Improved overall UI/UX design, theming.
- [ ] Comprehensive error message display and guidance.

## IV. Operational & Integration Enhancements

### Broader OpenMetadata Integration
- [ ] **Relationship Suggestion:** Use OpenMetadata lineage or relationship APIs to suggest potential relationships for the ZenBI MDL.
- [ ] **Tag/Glossary Term Integration:** Pull tags or glossary term definitions from OpenMetadata to enrich descriptions or properties in ZenBI MDL.
- [ ] **Two-way Sync (Ambitious):** Option to push ZenBI semantic definitions back to OpenMetadata.

### Deployment & Scalability
- [ ] Dockerization for easier deployment.
- [ ] Performance optimization for handling larger MDLs and more concurrent users.

### Extensibility
- [ ] Plugin architecture for adding new data sources or custom LLM providers more easily.
```
