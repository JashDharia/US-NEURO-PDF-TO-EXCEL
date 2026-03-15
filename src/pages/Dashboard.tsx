import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, BarChart3, TrendingUp, PieChart, Activity, DollarSign, ListFilter } from 'lucide-react';
import PlotComponent from 'react-plotly.js';

// Safe extraction for Vite/ESM default export handling
const Plot = (PlotComponent as any).default || PlotComponent;

interface JobDetail {
  id: string;
  created_at: string;
  file_names: string[];
  data: any[];
}

type ChartType = 'bar' | 'pie' | 'line';

export function Dashboard() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);

  // Chart Builder State
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [xAxisCol, setXAxisCol] = useState<string>('');
  const [yAxisCol, setYAxisCol] = useState<string>('');
  const [aggregation, setAggregation] = useState<'count' | 'sum' | 'avg'>('count');

  useEffect(() => {
    const fetchJobData = (jobId: string) => {
      fetch(`http://localhost:8000/api/history/${jobId}`)
        .then(res => res.json())
        .then(resData => {
          if (resData.status === 'success') {
            setJob(resData.job);
            if (resData.job.data && resData.job.data.length > 0) {
              const cols = Object.keys(resData.job.data[0]);
              const possibleX = cols.find(c => c.toLowerCase().includes('party') || c.toLowerCase().includes('outcome') || c.toLowerCase().includes('name'));
              if (possibleX) setXAxisCol(possibleX);
              else setXAxisCol(cols[0]);

              const possibleY = cols.find(c => c.toLowerCase().includes('amount') || c.toLowerCase().includes('offer'));
              if (possibleY) {
                 setYAxisCol(possibleY);
                 setAggregation('sum');
              } else {
                 setYAxisCol(cols[cols.length - 1]);
              }
            }
          }
        })
        .catch(err => console.error(err))
        .finally(() => setLoading(false));
    };

    if (!id) {
      // If no ID is given, fetch history and load the most recent job
      fetch('http://localhost:8000/api/history')
        .then(res => res.json())
        .then(data => {
          if (data.status === 'success' && data.history.length > 0) {
            fetchJobData(data.history[0].id);
          } else {
            setLoading(false);
          }
        })
        .catch(err => {
          console.error(err);
          setLoading(false);
        });
    } else {
      fetchJobData(id);
    }
  }, [id]);

  const columns = useMemo(() => {
    if (!job || !job.data || job.data.length === 0) return [];
    return Object.keys(job.data[0]).filter(k => k !== 'Source File');
  }, [job]);

  // --- Dynamic KPI Calculations ---
  const kpis = useMemo(() => {
    if (!job || !job.data) return null;
    let totalProviderOffer = 0;
    let totalInsurerOffer = 0;
    let providerWins = 0;
    let validOutcomes = 0;

    job.data.forEach(row => {
      // Clean currencies
      const parseAmount = (val: string) => {
        if (!val || val === 'N/A') return 0;
        return parseFloat(String(val).replace(/[^0-9.-]+/g, '')) || 0;
      };

      totalProviderOffer += parseAmount(row['Provider Offer Amount']);
      totalInsurerOffer += parseAmount(row['Insurance Offer Amount']);

      const outcome = String(row['Outcome'] || '').toLowerCase();
      if (outcome && outcome !== 'n/a') {
        validOutcomes++;
        // Very basic string check; assumes the Outcome logic was "Provider Win" or "Win by Default"
        if (outcome.includes('win') && !outcome.includes('insurer win') && !outcome.includes('loss')) {
           providerWins++;
        }
      }
    });

    return {
      totalRows: job.data.length,
      providerTotal: totalProviderOffer,
      insurerTotal: totalInsurerOffer,
      winRate: validOutcomes > 0 ? ((providerWins / validOutcomes) * 100).toFixed(1) : 'N/A'
    };
  }, [job]);

  // --- Dynamic Chart Calculation ---
  const chartData = useMemo(() => {
    if (!job || !job.data || !xAxisCol || !yAxisCol) return null;

    const grouped: Record<string, number[]> = {};

    job.data.forEach(row => {
      const xVal = String(row[xAxisCol] || 'Unknown');
      
      let yVal = 1; // Default for count
      if (aggregation !== 'count') {
        const rawY = row[yAxisCol];
        yVal = parseFloat(String(rawY).replace(/[^0-9.-]+/g, '')) || 0;
      }

      if (!grouped[xVal]) grouped[xVal] = [];
      grouped[xVal].push(yVal);
    });

    const xLabels = Object.keys(grouped);
    const yValues = xLabels.map(x => {
      const vals = grouped[x];
      if (aggregation === 'count') return vals.length;
      const sum = vals.reduce((a, b) => a + b, 0);
      if (aggregation === 'avg') return sum / vals.length;
      return sum;
    });

    if (chartType === 'pie') {
      return [{
        values: yValues,
        labels: xLabels,
        type: 'pie',
        marker: { colors: ['#0f172a', '#3b82f6', '#f97316', '#10b981', '#6366f1'] }
      }];
    }

    return [{
      x: xLabels,
      y: yValues,
      type: chartType,
      marker: { color: chartType === 'bar' ? '#3b82f6' : '#f97316' }
    }];

  }, [job, chartType, xAxisCol, yAxisCol, aggregation]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-10 h-10 border-4 border-brand-blue/30 border-t-brand-blue rounded-full animate-spin" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 text-center px-6">
        <Activity size={48} className="text-slate-300 mb-4" />
        <h2 className="text-2xl font-bold text-slate-700">Dashboard Not Found</h2>
        <p className="text-slate-500 mt-2 mb-6">We couldn't locate the data for this extraction batch.</p>
        <button onClick={() => navigate('/history')} className="px-6 py-2 bg-brand-navy text-white rounded-lg">
          Back to History
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 pb-20">
      
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <button 
            onClick={() => navigate('/history')}
            className="flex items-center gap-2 text-slate-500 hover:text-brand-blue transition-colors mb-2 text-sm font-medium"
          >
            <ArrowLeft size={16} /> Back to History
          </button>
          <h2 className="text-3xl font-bold text-brand-navy flex items-center gap-3">
            <BarChart3 className="text-brand-blue" />
            Interactive Analytics Dashboard
          </h2>
          <p className="text-slate-500 mt-1 flex items-center gap-2">
            Batch processed on {new Date(job.created_at).toLocaleString()}
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      {kpis && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
              <Activity size={24} />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 mb-1">Total Records Extracted</p>
              <h3 className="text-2xl font-bold text-slate-800">{kpis.totalRows}</h3>
            </div>
          </div>
          
          <div className="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-green-50 text-green-600 flex items-center justify-center shrink-0">
              <TrendingUp size={24} />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 mb-1">Estimated Win Rate</p>
              <h3 className="text-2xl font-bold text-slate-800">{kpis.winRate}{kpis.winRate !== 'N/A' && '%'}</h3>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-orange-50 text-orange-600 flex items-center justify-center shrink-0">
              <DollarSign size={24} />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 mb-1">Total Provider Offers</p>
              <h3 className="text-xl font-bold text-slate-800">${kpis.providerTotal.toLocaleString(undefined, {minimumFractionDigits: 2})}</h3>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-slate-50 text-slate-600 flex items-center justify-center shrink-0">
              <DollarSign size={24} />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 mb-1">Total Insurer Offers</p>
              <h3 className="text-xl font-bold text-slate-800">${kpis.insurerTotal.toLocaleString(undefined, {minimumFractionDigits: 2})}</h3>
            </div>
          </div>
        </div>
      )}

      {/* Interactive Chart Builder */}
      <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
        
        {/* Chart Controls */}
        <div className="bg-slate-50 px-8 py-6 border-b border-slate-100 grid grid-cols-1 md:grid-cols-4 gap-6">
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Chart Type</label>
            <div className="flex bg-white rounded-lg border border-slate-200 p-1">
              {(['bar', 'line', 'pie'] as ChartType[]).map(type => (
                <button
                  key={type}
                  onClick={() => setChartType(type)}
                  className={`flex-1 py-1.5 text-sm font-medium rounded-md capitalize flex items-center justify-center gap-1.5 transition-colors ${
                    chartType === type ? 'bg-brand-blue text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {type === 'bar' && <BarChart3 size={14} />}
                  {type === 'line' && <TrendingUp size={14} />}
                  {type === 'pie' && <PieChart size={14} />}
                  {type}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Category (X-Axis)</label>
            <select 
              value={xAxisCol}
              onChange={(e) => setXAxisCol(e.target.value)}
              className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-blue/50 outline-none"
            >
              <option value="">Select Column...</option>
              {columns.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Value (Y-Axis)</label>
            <select 
              value={yAxisCol}
              onChange={(e) => setYAxisCol(e.target.value)}
              className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-blue/50 outline-none"
            >
              <option value="">Select Column...</option>
              {columns.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Aggregation</label>
            <select 
              value={aggregation}
              onChange={(e) => setAggregation(e.target.value as any)}
              className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-blue/50 outline-none"
            >
              <option value="count">Count (Frequency)</option>
              <option value="sum">Sum (Total)</option>
              <option value="avg">Average</option>
            </select>
          </div>
        </div>

        {/* Plot Area */}
        <div className="p-8 aspect-[21/9] min-h-[500px] w-full relative">
          {chartData && chartData[0] ? (
            <Plot
              data={chartData as any}
              layout={{
                autosize: true,
                margin: { l: 60, r: 30, t: 30, b: 120 },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { family: 'Inter, sans-serif', color: '#475569' },
                xaxis: { 
                  title: { text: xAxisCol },
                  tickangle: -45,
                  automargin: true,
                  gridcolor: '#f1f5f9'
                },
                yaxis: { 
                  title: { text: aggregation === 'count' ? 'Count' : `${aggregation.toUpperCase()} of ${yAxisCol}` },
                  automargin: true,
                  gridcolor: '#f1f5f9'
                },
                hovermode: 'closest'
              }}
              useResizeHandler={true}
              style={{ width: '100%', height: '100%' }}
              config={{ responsive: true, displayModeBar: true }}
            />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
              <ListFilter size={48} className="mb-4 opacity-50" />
              <p>Select an X and Y axis to build your chart</p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
