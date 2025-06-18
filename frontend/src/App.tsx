import React, { useState, FormEvent } from 'react';
import QueryResultChart from './components/QueryResultChart'; // Import the chart component
import './App.css';

interface QueryResult {
  [key: string]: any;
}

interface ChartSuggestion {
  chart_type: 'bar' | 'line' | 'pie' | 'table' | null | string;
  x_column: string;
  y_columns: string[];
  title?: string;
}

interface ApiResponse {
  natural_language_query: string;
  zensql_query?: string | null;
  final_sql_query?: string | null;
  mdl_context_used?: string | null;
  query_results?: QueryResult[] | null;
  chart_suggestion?: ChartSuggestion | null; // Added chart_suggestion
  error_message?: string | null;
}

function App() {
  const [nlQuery, setNlQuery] = useState<string>('');
  const [apiResponse, setApiResponse] = useState<ApiResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsLoading(true);
    setErrorMsg('');
    setApiResponse(null);

    if (!nlQuery.trim()) {
      setErrorMsg('Please enter a natural language query.');
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch('/api/query/execute-natural-language', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ natural_language_query: nlQuery }),
      });
      const data: ApiResponse = await response.json();
      if (!response.ok) {
        setErrorMsg(data.error_message || data.detail || `Error ${response.status}: ${response.statusText}`);
        setApiResponse(data);
      } else {
        setApiResponse(data);
        if (data.error_message) {
          setErrorMsg(data.error_message);
        }
      }
    } catch (error) {
      console.error('Fetch error:', error);
      setErrorMsg('Failed to fetch data from the server. Is the backend running?');
    } finally {
      setIsLoading(false);
    }
  };

  const setupSampleDb = async () => {
    setIsLoading(true);
    setErrorMsg('');
    setApiResponse(null);
    try {
      const response = await fetch('/api/admin/setup-sample-db', { method: 'GET' });
      const data = await response.json();
      if (!response.ok) {
        setErrorMsg(data.detail || data.message || `Error ${response.status}: ${response.statusText}`);
      } else {
        alert(data.message || "Sample DB setup initiated successfully!");
      }
    } catch (error) {
      console.error('Setup DB error:', error);
      setErrorMsg('Failed to setup sample DB. Is the backend running?');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>ZenBI Query Interface</h1>
        <button onClick={setupSampleDb} disabled={isLoading} className="setup-db-button">
          {isLoading ? 'Processing...' : 'Setup/Reset Sample Database'}
        </button>
      </header>

      <main className="main-content">
        <div className="query-input-section">
          <form onSubmit={handleSubmit}>
            <div>
              <label htmlFor="nlQuery">Enter your Natural Language Query:</label>
              <textarea
                id="nlQuery"
                value={nlQuery}
                onChange={(e) => setNlQuery(e.target.value)}
                rows={3}
                disabled={isLoading}
              />
            </div>
            <button type="submit" disabled={isLoading}>
              {isLoading ? 'Processing...' : 'Execute Query'}
            </button>
          </form>
        </div>

        {isLoading && <div className="loading-message">Loading...</div>}
        {errorMsg && <div className="error-message">Error: {errorMsg}</div>}

        {apiResponse && (
          <div className="results-display">
            <div className="query-details-grid">
              <div className="result-section nlq-section">
                <h3>Natural Language Query:</h3>
                <pre>{apiResponse.natural_language_query}</pre>
              </div>

              {apiResponse.zensql_query && (
                <div className="result-section zensql-section">
                  <h3>Generated ZenSQL:</h3>
                  <pre>{apiResponse.zensql_query}</pre>
                </div>
              )}

              {apiResponse.final_sql_query && (
                <div className="result-section finalsql-section">
                  <h3>Transpiled SQL Query:</h3>
                  <pre>{apiResponse.final_sql_query}</pre>
                </div>
              )}
            </div> {/* End of query-details-grid */}

            {(apiResponse.query_results || apiResponse.chart_suggestion) && (
                 <div className="data-visualization-area">
                    {apiResponse.query_results && apiResponse.query_results.length > 0 && (
                    <div className="result-section table-section">
                        <h3>Query Results Table:</h3>
                        <table>
                        <thead>
                            <tr>
                            {Object.keys(apiResponse.query_results[0]).map((key) => (
                                <th key={key}>{key}</th>
                            ))}
                            </tr>
                        </thead>
                        <tbody>
                            {apiResponse.query_results.map((row, index) => (
                            <tr key={index}>
                                {Object.values(row).map((value, i) => (
                                <td key={i}>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</td>
                                ))}
                            </tr>
                            ))}
                        </tbody>
                        </table>
                    </div>
                    )}
                    {apiResponse.query_results && apiResponse.query_results.length === 0 && (
                        <div className="result-section">
                            <h3>Query Results:</h3>
                            <p>Query executed successfully, but returned no data.</p>
                        </div>
                    )}

                    {apiResponse.chart_suggestion && apiResponse.query_results && apiResponse.query_results.length > 0 && (
                        <div className="result-section chart-section">
                            <QueryResultChart
                                data={apiResponse.query_results}
                                chartSuggestion={apiResponse.chart_suggestion}
                            />
                        </div>
                    )}
                     {apiResponse.chart_suggestion && apiResponse.query_results && apiResponse.query_results.length === 0 && (
                        <div className="result-section chart-section">
                             <p>No data to display in chart.</p>
                        </div>
                    )}
                 </div>
            )}


            {apiResponse.mdl_context_used && (
              <div className="result-section context-section">
                <h3>MDL Context Used (for LLM):</h3>
                <pre className="context-box">
                  {apiResponse.mdl_context_used}
                </pre>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
