import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  LineChart,
  PieChart,
  Bar,
  Line,
  Pie,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
  LabelList // For Pie chart labels
} from 'recharts';

interface ChartSuggestion {
  chart_type: 'bar' | 'line' | 'pie' | 'table' | null | string; // Allow string for flexibility if LLM gives other types
  x_column: string;
  y_columns: string[]; // Array for multi-series, but most basic charts here use first one
  title?: string;
}

interface QueryResultChartProps {
  data: any[]; // Array of data objects from the query
  chartSuggestion: ChartSuggestion | null;
}

// Helper to generate random colors for Pie chart, can be expanded
const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82Ca9D', '#FF5733', '#C70039', '#900C3F', '#581845'];

const QueryResultChart: React.FC<QueryResultChartProps> = ({ data, chartSuggestion }) => {
  if (!chartSuggestion || !data || data.length === 0) {
    return <p>No chart data or suggestion available.</p>;
  }

  const { chart_type, x_column, y_columns, title } = chartSuggestion;

  if (!x_column || !y_columns || y_columns.length === 0) {
    return <p>Chart suggestion is incomplete (missing x_column or y_columns).</p>;
  }

  // Check if specified columns exist in data
  const firstDataItem = data[0];
  if (!firstDataItem.hasOwnProperty(x_column) || !firstDataItem.hasOwnProperty(y_columns[0])) {
     console.warn("Data for chart is missing specified x_column or y_column(s).", {x_column, y_columns, firstDataItem});
     return <p>Data is missing the columns specified for the chart ({x_column}, {y_columns.join(', ')}).</p>;
  }

  // Ensure y_column data is numeric for charts that need it (bar, line, pie)
  if (chart_type !== 'table') {
    const sampleYValue = parseFloat(firstDataItem[y_columns[0]]);
    if (isNaN(sampleYValue)) {
        console.warn(`Y-axis data ('${y_columns[0]}') is not numeric, which may cause issues with ${chart_type} chart.`);
        // Allow rendering to proceed, Recharts might handle some cases or show errors.
    }
  }


  const chartTitle = title || "Generated Chart";

  const renderChart = () => {
    switch (chart_type) {
      case 'bar':
        return (
          <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 50 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={x_column} angle={-30} textAnchor="end" interval={0} name={x_column}/>
            <YAxis name={y_columns[0]}/>
            <Tooltip />
            <Legend />
            {y_columns.map((yCol, index) => (
                <Bar key={yCol} dataKey={yCol} fill={COLORS[index % COLORS.length]} name={yCol}/>
            ))}
          </BarChart>
        );
      case 'line':
        return (
          <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 50 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={x_column} angle={-30} textAnchor="end" interval={0} name={x_column}/>
            <YAxis name={y_columns[0]}/>
            <Tooltip />
            <Legend />
            {y_columns.map((yCol, index) => (
                 <Line key={yCol} type="monotone" dataKey={yCol} stroke={COLORS[index % COLORS.length]} name={yCol} />
            ))}
          </LineChart>
        );
      case 'pie':
        // Pie chart usually takes one measure (y_columns[0]) and one dimension (x_column for names)
        // Recharts Pie component expects data in a specific format where each item has a 'name' and 'value' key.
        // We need to transform our data if it's not already in that format.
        // For simplicity, let's assume data is already suitable or we map it.
        // If y_columns[0] is the value and x_column is the name:
        const pieData = data.map(item => ({
            name: item[x_column],
            value: parseFloat(item[y_columns[0]]) // Ensure value is a number
        })).filter(item => !isNaN(item.value)); // Filter out non-numeric values

        if (pieData.some(item => item.value < 0)) {
            return <p>Pie chart cannot render negative values. Data for '{y_columns[0]}' contains negative numbers.</p>;
        }

        return (
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              labelLine={false}
              // label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`} // Example label
              label = {<CustomizedPieLabel data={pieData} />}
              outerRadius={120}
              fill="#8884d8"
              dataKey="value" // This must be "value" for the Pie component after transformation
              nameKey="name"   // This must be "name"
            >
              {pieData.map((_entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value, name) => [value, name]} />
            <Legend />
          </PieChart>
        );
      case 'table':
      case null:
      default:
        return <p>Chart type '{chart_type}' is not supported or no specific chart suggested.</p>;
    }
  };

  return (
    <div style={{ width: '100%', height: 400 }}>
      <h4>{chartTitle}</h4>
      <ResponsiveContainer>
        {renderChart()}
      </ResponsiveContainer>
    </div>
  );
};

// Custom label for Pie chart to avoid clutter
const RADIAN = Math.PI / 180;
const CustomizedPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index, data }: any) => {
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);
    const currentData = data[index]; // Access the current data item by index

    // Only render label if percent is significant to avoid clutter
    if ((percent * 100) < 5) return null;

    return (
        <text x={x} y={y} fill="white" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central">
            {`${currentData.name} (${(percent * 100).toFixed(0)}%)`}
        </text>
    );
};


export default QueryResultChart;
