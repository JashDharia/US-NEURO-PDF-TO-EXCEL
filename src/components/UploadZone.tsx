import React, { useCallback } from 'react';
import { UploadCloud, File as FileIcon, X } from 'lucide-react';
import { clsx } from 'clsx';

interface UploadZoneProps {
  files: File[];
  setFiles: React.Dispatch<React.SetStateAction<File[]>>;
}

export function UploadZone({ files, setFiles }: UploadZoneProps) {
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
      if (droppedFiles.length > 0) {
        setFiles((prev) => [...prev, ...droppedFiles]);
      }
    }
  }, [setFiles]);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files).filter(f => f.type === 'application/pdf');
      setFiles((prev) => [...prev, ...selectedFiles]);
    }
  };

  const removeFile = (idxToRemove: number) => {
    setFiles(files.filter((_, idx) => idx !== idxToRemove));
  };

  return (
    <div className="space-y-4">
      <div 
        onDragOver={onDragOver}
        onDrop={onDrop}
        className={clsx(
          "border-2 border-dashed rounded-3xl p-10 text-center transition-all cursor-pointer relative overflow-hidden group",
          "bg-slate-50/50 hover:bg-slate-100/50 border-slate-300 hover:border-brand-blue hover:shadow-inner"
        )}
      >
        <input 
          type="file" 
          accept="application/pdf"
          multiple
          onChange={onFileChange}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
        />
        <div className="w-16 h-16 mx-auto rounded-full bg-white shadow-sm flex items-center justify-center text-brand-blue mb-4 group-hover:scale-110 group-hover:bg-brand-blue/10 transition-all duration-300">
          <UploadCloud size={28} />
        </div>
        <h3 className="text-base font-medium text-slate-800 mb-1">Drag & Drop your PDFs here</h3>
        <p className="text-sm text-slate-500 mb-4 max-w-sm mx-auto">
          Multiple PDF files can be processed at once.
        </p>
        <div className="inline-flex items-center justify-center px-5 py-2 rounded-full bg-slate-200 text-slate-700 font-medium text-sm group-hover:bg-brand-blue group-hover:text-white transition-colors">
          Browse Files
        </div>
      </div>

      {files.length > 0 && (
        <div className="space-y-2 max-h-[220px] overflow-y-auto pr-2 custom-scrollbar">
          {files.map((f, idx) => (
            <div key={idx} className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between group transition-all hover:border-brand-blue/50">
              <div className="flex items-center gap-3 overflow-hidden">
                <div className="w-10 h-10 shrink-0 rounded-lg bg-brand-blue/10 flex items-center justify-center text-brand-blue">
                  <FileIcon size={20} />
                </div>
                <div className="min-w-0">
                  <p className="font-semibold text-slate-800 text-sm truncate">{f.name}</p>
                  <p className="text-xs text-slate-500">{(f.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
              </div>
              <button 
                onClick={() => removeFile(idx)}
                className="w-8 h-8 shrink-0 rounded-full flex items-center justify-center text-slate-400 hover:bg-red-50 hover:text-red-500 transition-colors"
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
