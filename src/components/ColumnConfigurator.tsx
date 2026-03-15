import { useState } from 'react';
import { Plus, X, GripVertical, FileText, Pencil, Check } from 'lucide-react';

export interface ColumnDef {
  name: string;
  logic: string;
}

interface ColumnConfiguratorProps {
  columns: ColumnDef[];
  setColumns: (cols: ColumnDef[]) => void;
  files: File[];
}

export function ColumnConfigurator({ columns, setColumns, files }: ColumnConfiguratorProps) {
  const [newColName, setNewColName] = useState('');
  const [newColLogic, setNewColLogic] = useState('');
  
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [editColName, setEditColName] = useState('');
  const [editColLogic, setEditColLogic] = useState('');

  const [isGenerating, setIsGenerating] = useState(false);

  const addColumn = () => {
    if (newColName.trim() && !columns.find(c => c.name === newColName.trim())) {
      setColumns([...columns, { name: newColName.trim(), logic: newColLogic.trim() }]);
      setNewColName('');
      setNewColLogic('');
    }
  };

  const handleAutoGenerate = async () => {
    if (!newColName.trim()) return;
    setIsGenerating(true);
    
    const formData = new FormData();
    formData.append('name', newColName.trim());
    
    // Pass the first file as context if it exists
    if (files && files.length > 0) {
      formData.append('file', files[0]);
    }

    try {
      const res = await fetch('/api/generate-logic', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.status === 'success' && data.logic) {
        setNewColLogic(data.logic);
        
        // Show an alert if the AI warns that the column isn't found in the document
        if (data.logic.startsWith('Warning:')) {
            alert(data.logic);
        }
      }
    } catch (err) {
      console.error("Failed to generate logic:", err);
    } finally {
      setIsGenerating(false);
    }
  };

  const startEdit = (idx: number) => {
    setEditingIdx(idx);
    setEditColName(columns[idx].name);
    setEditColLogic(columns[idx].logic);
  };

  const saveEdit = () => {
    if (editingIdx !== null && editColName.trim()) {
      const newCols = [...columns];
      newCols[editingIdx] = { name: editColName.trim(), logic: editColLogic.trim() };
      setColumns(newCols);
      setEditingIdx(null);
    }
  };

  const removeColumn = (idx: number) => {
    setColumns(columns.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-4">
      <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 max-h-[400px] overflow-y-auto space-y-3 custom-scrollbar">
        {columns.map((col, idx) => (
          <div key={idx} className="flex items-start gap-3 bg-white p-4 rounded-xl border border-slate-100 shadow-sm group">
            <GripVertical size={16} className="text-slate-300 cursor-grab mt-1 shrink-0" />
            
            {editingIdx === idx ? (
              <div className="flex-1 space-y-2">
                <input 
                  type="text"
                  value={editColName}
                  onChange={(e) => setEditColName(e.target.value)}
                  className="w-full bg-white border border-brand-blue/30 rounded px-2 py-1 text-sm font-medium focus:outline-none focus:ring-1 focus:ring-brand-blue"
                />
                <textarea 
                  value={editColLogic}
                  onChange={(e) => setEditColLogic(e.target.value)}
                  className="w-full bg-white border border-brand-blue/30 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-blue min-h-[40px] resize-none"
                />
              </div>
            ) : (
              <div className="flex-1 space-y-1">
                <span className="block font-medium text-slate-700 text-sm">{col.name}</span>
                {col.logic ? (
                  <span className="block text-xs text-slate-500 bg-slate-50 p-2 rounded-lg border border-slate-100 flex items-start gap-2">
                    <FileText size={14} className="shrink-0 text-brand-blue" /> 
                    <span className="leading-relaxed">{col.logic}</span>
                  </span>
                ) : (
                  <span className="block text-xs text-slate-400 italic">No specific logic provided. AI will auto-extract.</span>
                )}
              </div>
            )}

            <div className="flex items-center gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
              {editingIdx === idx ? (
                <button 
                  onClick={saveEdit}
                  className="p-1.5 text-green-600 bg-green-50 rounded-md hover:bg-green-100 transition-colors"
                >
                  <Check size={14} />
                </button>
              ) : (
                <button 
                  onClick={() => startEdit(idx)}
                  className="p-1.5 text-brand-blue bg-blue-50 rounded-md hover:bg-blue-100 transition-colors"
                >
                  <Pencil size={14} />
                </button>
              )}
              <button 
                onClick={() => removeColumn(idx)}
                className="p-1.5 text-red-500 bg-red-50 rounded-md hover:bg-red-100 transition-colors"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        ))}
        {columns.length === 0 && (
          <p className="text-center text-sm text-slate-400 py-4">No columns defined. Add one below.</p>
        )}
      </div>

      <div className="flex flex-col gap-2 p-3 bg-white rounded-xl border border-slate-200">
        <div className="flex items-center gap-2">
          <input 
            type="text"
            value={newColName}
            onChange={(e) => setNewColName(e.target.value)}
            placeholder="Column Name (e.g. Diagnosis)"
            className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/50 focus:border-brand-blue transition-all"
          />
          <button
            onClick={handleAutoGenerate}
            disabled={!newColName.trim() || isGenerating}
            className="flex items-center gap-1 px-3 py-2 bg-purple-50 hover:bg-purple-100 text-purple-600 rounded-lg text-sm font-medium transition-colors border border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            title="AI will automatically write extraction instructions based on the column name"
          >
            {isGenerating ? <div className="w-4 h-4 border-2 border-purple-600/30 border-t-purple-600 rounded-full animate-spin" /> : '✨ Auto-write logic'}
          </button>
        </div>
        <textarea 
          value={newColLogic}
          onChange={(e) => setNewColLogic(e.target.value)}
          placeholder="Extraction Logic (e.g. Extract the primary ICD-10 diagnosis. Return N/A if missing.)"
          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/50 focus:border-brand-blue transition-all min-h-[60px] resize-none"
        />
        <button 
          onClick={addColumn}
          disabled={!newColName.trim()}
          className="w-full py-2 bg-brand-navy hover:bg-brand-navy/90 text-white rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
        >
          <Plus size={16} /> Add Column
        </button>
      </div>
    </div>
  );
}
