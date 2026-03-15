import { useEffect, useState } from 'react';
import { Activity, File, Calendar, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface HistoryJob {
  id: string;
  created_at: string;
  file_names: string[];
}

export function History() {
  const [jobs, setJobs] = useState<HistoryJob[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetch('/api/history')
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') setJobs(data.history);
      })
      .catch(err => console.error("Failed to fetch history:", err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-6 mt-12 pb-20">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-brand-navy flex items-center gap-3">
          <Activity className="text-brand-blue" size={32} />
          Extraction History
        </h2>
        <p className="text-slate-500 mt-2">View recently processed document batches and access their analytics dashboards.</p>
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <div className="w-8 h-8 border-4 border-brand-blue/30 border-t-brand-blue rounded-full animate-spin" />
        </div>
      ) : jobs.length === 0 ? (
        <div className="bg-white rounded-3xl p-12 text-center shadow-sm border border-slate-100">
          <Calendar className="mx-auto text-slate-300 mb-4" size={48} />
          <h3 className="text-xl font-semibold text-slate-700">No History Yet</h3>
          <p className="text-slate-500 mt-2">Upload and extract your first batch of documents to see them here.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {jobs.map(job => (
            <div 
              key={job.id} 
              onClick={() => navigate(`/dashboard/${job.id}`)}
              className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 hover:border-brand-blue/30 hover:shadow-md cursor-pointer transition-all group flex items-center justify-between"
            >
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm text-slate-500 font-medium">
                  <Calendar size={16} />
                  {new Date(job.created_at).toLocaleString()}
                </div>
                <div className="flex flex-wrap gap-2">
                  {job.file_names.map((name, idx) => (
                    <span key={idx} className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-50 text-slate-700 text-sm rounded-lg border border-slate-100">
                      <File size={14} className="text-brand-orange" />
                      {name}
                    </span>
                  ))}
                </div>
              </div>
              <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-brand-blue group-hover:bg-brand-blue group-hover:text-white transition-colors shrink-0">
                <ChevronRight size={20} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
