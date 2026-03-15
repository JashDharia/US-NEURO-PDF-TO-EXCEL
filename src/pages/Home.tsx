import { useState } from 'react';
import { UploadZone } from '../components/UploadZone';
import { ColumnConfigurator, type ColumnDef } from '../components/ColumnConfigurator';
import { FileUp, Download, Settings, Activity, MessageSquarePlus, CheckCircle2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [columns, setColumns] = useState<ColumnDef[]>([
    { name: 'Date', logic: 'Extract the official notification date, determination date, or "period begins on" date. Format as YYYY-MM-DD. Search carefully.' },
    { name: 'IDR Reference Number', logic: 'Extract the IDR reference number if present' },
    { name: 'Determination Number', logic: 'Extract the determination number or block number if multiple exist' },
    { name: 'IDRE Name', logic: 'Extract the name of the Independent Dispute Resolution Entity (IDRE)' },
    { name: 'Insurance Company Name', logic: 'Extract the name of the insurance company. This is usually the non-initiating party.' },
    { name: 'Prevailing Party', logic: 'Extract the name of the party that prevailed or won.' },
    { name: 'Item or Service Code', logic: 'Extract the CPT or service code associated with the claim' },
    { name: 'Claim Number', logic: 'Extract the claim number' },
    { name: 'Provider Offer Amount', logic: 'Extract the dollar amount offered by the provider/initiating party' },
    { name: 'Insurance Offer Amount', logic: 'Extract the dollar amount offered by the insurance company. If missing, assume 0.00' },
    { name: 'Prevailing Offer', logic: 'Extract the final chosen prevailing dollar amount' },
    { name: 'Xs - Initiating Party', logic: 'Count how many checkmarks or Xs the Initiating Party (provider) received for submitting evidence' },
    { name: 'Xs - Non-Initiating Party', logic: 'Count how many checkmarks or Xs the Non-Initiating Party (insurer) received for submitting evidence' },
    { name: 'Outcome', logic: 'If IDR: Compare prevailing party against insurer name. Provider Win = provider prevailed & insurer has Xs. Win by Default = provider prevailed & insurer has 0 Xs. Loss = insurer prevailed & provider has Xs. Loss by Default = insurer prevailed & provider has 0 Xs. For non-IDR, just summarize the outcome.' }
  ]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [excelUrl, setExcelUrl] = useState<string | null>(null);
  
  const [feedbackRule, setFeedbackRule] = useState('');
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);

  const handleExtract = async () => {
    if (files.length === 0) return;
    setIsProcessing(true);
    setExcelUrl(null);
    setFeedbackSuccess(false);
    setFeedbackRule('');
    
    try {
      const formData = new FormData();
      files.forEach((file: File) => formData.append('files', file));
      formData.append('columns', JSON.stringify(columns));

      const response = await fetch('/api/extract', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Extraction failed');
      }

      const data = await response.json();
      if (data.status === 'success' && data.excel_url && data.job_id) {
        setExcelUrl(data.excel_url);
        
        try {
          // The absolute most bulletproof way for Chrome cross-origin downloads:
          // 1. Fetch the raw binary array buffer
          const downloadResponse = await fetch(data.excel_url);
          const arrayBuffer = await downloadResponse.arrayBuffer();
          
          // 2. Force the strict Excel MIME type so Chrome does not corrupt the encoding
          const blob = new Blob([arrayBuffer], { 
            type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
          });
          
          // 3. Trigger download via transient anchor
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.style.display = 'none';
          a.href = url;
          a.download = data.excel_url.split('file=')[1] || 'Extraction.xlsx';
          document.body.appendChild(a);
          a.click();
          
          // Cleanup
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        } catch (downloadErr) {
          console.error("Download failed:", downloadErr);
          alert("Chrome blocked the automatic download. Please check your console.");
        }
        
        // Removed auto-navigate so User stays on Home Page.
      }
    } catch (error) {
      console.error(error);
      alert('An error occurred during extraction.');
    } finally {
      setIsProcessing(false);
    }
  };

  const submitFeedback = async () => {
    if (!feedbackRule.trim()) return;
    setIsSubmittingFeedback(true);
    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ rule: feedbackRule.trim() }),
      });
      if (response.ok) {
        setFeedbackSuccess(true);
        setFeedbackRule('');
        setTimeout(() => setFeedbackSuccess(false), 5000);
      } else {
        alert('Failed to submit learning rule.');
      }
    } catch (error) {
      console.error(error);
      alert('Error connecting to feedback API.');
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  return (
    <main className="relative z-10 max-w-5xl mx-auto px-6 mt-12 grid grid-cols-1 lg:grid-cols-12 gap-8">
      {/* Left Column: Upload */}
      <div className="lg:col-span-7 space-y-6">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white/60 backdrop-blur-xl border border-white p-8 rounded-3xl shadow-xl shadow-slate-200/50"
        >
          <div className="mb-6">
            <h2 className="text-2xl font-semibold text-brand-navy flex items-center gap-2">
              <FileUp className="text-brand-blue" />
              Document Upload
            </h2>
            <p className="text-slate-500 mt-1">Upload a medical PDF to extract intelligent, structured insights.</p>
          </div>
          
          <UploadZone files={files} setFiles={setFiles} />
        </motion.div>
      </div>

      {/* Right Column: Configuration & Action */}
      <div className="lg:col-span-5 space-y-6">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white/60 backdrop-blur-xl border border-white p-8 rounded-3xl shadow-xl shadow-slate-200/50"
        >
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-brand-navy flex items-center gap-2">
                <Settings size={20} className="text-brand-orange" />
                Output Columns
              </h2>
              <p className="text-sm text-slate-500 mt-1">Define your Excel structure</p>
            </div>
          </div>

          <ColumnConfigurator columns={columns} setColumns={setColumns} files={files} />

        </motion.div>

        {/* Action Card */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-gradient-to-br from-brand-navy to-slate-900 p-8 rounded-3xl shadow-2xl shadow-brand-navy/30 text-white relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-brand-blue/20 blur-3xl rounded-full" />
          <div className="absolute bottom-0 left-0 w-32 h-32 bg-brand-orange/20 blur-3xl rounded-full" />
          
          <h3 className="text-lg font-medium text-white/90 mb-2 relative z-10">Ready to Process</h3>
          <p className="text-sm text-slate-300 mb-6 relative z-10">
            The AI engine will map the PDF contents into {columns.length} structured columns.
          </p>

          <button
            onClick={handleExtract}
            disabled={files.length === 0 || isProcessing}
            className={`relative z-10 w-full py-4 px-6 rounded-2xl font-semibold text-lg flex items-center justify-center gap-2 transition-all duration-300 ${
              files.length === 0 ? 'bg-white/10 text-white/50 cursor-not-allowed' : 
              isProcessing ? 'bg-brand-blue/50 text-white cursor-wait' :
              'bg-brand-blue hover:bg-blue-500 text-white shadow-lg transform hover:-translate-y-1'
            }`}
          >
            {isProcessing ? (
              <>
                <Activity className="animate-pulse" />
                Processing...
              </>
            ) : (
              <>
                <Download />
                Extract to Excel
              </>
            )}
          </button>
        </motion.div>

        {/* Feedback Form */}
        {excelUrl && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 space-y-6"
          >
            <div className="bg-white rounded-3xl shadow-sm border border-brand-orange/20 overflow-hidden relative z-10">
              <div className="bg-gradient-to-r from-orange-50 to-brand-orange/5 px-6 py-4 border-b border-brand-orange/10 flex items-center gap-3">
                <div className="p-2 bg-brand-orange/10 rounded-lg text-brand-orange">
                  <MessageSquarePlus size={20} />
                </div>
                <div>
                  <h3 className="font-bold text-slate-800">Improve AI Extraction</h3>
                  <p className="text-sm text-slate-500">Notice a mistake? Teach the AI a new rule for future documents.</p>
                </div>
              </div>
              <div className="p-6">
                <div className="flex gap-3">
                  <textarea 
                    value={feedbackRule}
                    onChange={(e) => setFeedbackRule(e.target.value)}
                    placeholder="e.g. 'If DOB is missing, look for Date of Birth'"
                    className="flex-1 border border-slate-200 rounded-xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-orange/50 resize-none min-h-[80px]"
                  />
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <AnimatePresence>
                    {feedbackSuccess && (
                      <motion.div
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        className="flex items-center gap-2 text-green-600 text-sm font-medium"
                      >
                        <CheckCircle2 size={16} /> Rule saved successfully!
                      </motion.div>
                    )}
                  </AnimatePresence>
                  <button 
                    onClick={submitFeedback}
                    disabled={isSubmittingFeedback || !feedbackRule.trim()}
                    className={`ml-auto px-6 py-2.5 rounded-full font-medium text-sm transition-all shadow-sm ${
                      isSubmittingFeedback || !feedbackRule.trim() 
                      ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                      : 'bg-brand-orange hover:bg-orange-500 text-white hover:shadow-md'
                    }`}
                  >
                    {isSubmittingFeedback ? 'Saving...' : 'Teach AI'}
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </main>
  );
}
