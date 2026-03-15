import { BrowserRouter as Router, Routes, Route, Link, Navigate, useLocation } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { Home } from './pages/Home';
import { History } from './pages/History';
import { Dashboard } from './pages/Dashboard';
import { Component, type ErrorInfo, type ReactNode } from 'react';

class ErrorBoundary extends Component<{children: ReactNode}, {hasError: boolean, error: Error | null}> {
  constructor(props: {children: ReactNode}) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) { return { hasError: true, error }; }
  componentDidCatch(error: Error, errorInfo: ErrorInfo) { console.error("Caught:", error, errorInfo); }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-10 text-red-500 font-mono">
          <h1 className="text-2xl font-bold mb-4">React Crash Detected:</h1>
          <pre className="bg-red-50 p-4 rounded-lg overflow-auto">{this.state.error?.toString()}</pre>
          <pre className="bg-slate-100 p-4 rounded-lg overflow-auto text-slate-800 mt-4 text-xs">{this.state.error?.stack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

function Navigation() {
  const location = useLocation();
  const getNavClass = (path: string) => {
    return `transition-colors px-3 py-1 rounded-full ${
      location.pathname.startsWith(path) 
      ? 'bg-brand-blue/10 text-brand-blue font-semibold' 
      : 'text-slate-600 hover:text-brand-blue'
    }`;
  };

  return (
    <nav className="flex gap-2 text-sm font-medium">
      <Link to="/home" className={getNavClass('/home')}>Extractor</Link>
      <Link to="/history" className={getNavClass('/history')}>History</Link>
      <Link to="/dashboard" className={getNavClass('/dashboard')}>Dashboard</Link>
    </nav>
  );
}

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-brand-blue selection:text-white">
        {/* Background Decorative Elements */}
        <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-brand-blue/10 blur-[120px]" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-brand-orange/10 blur-[120px]" />
        </div>

        {/* Global Header */}
        <header className="sticky top-0 z-50 backdrop-blur-md bg-white/70 border-b border-white/20 shadow-sm">
          <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <Link to="/home" className="flex items-center gap-3 group">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-navy to-brand-blue flex items-center justify-center text-white shadow-lg shadow-brand-blue/20 group-hover:scale-105 transition-transform">
                <Activity size={24} />
              </div>
              <div>
                <h1 className="text-xl font-bold text-brand-navy leading-tight tracking-tight">US NEURO</h1>
                <p className="text-xs text-slate-500 font-medium tracking-wide">PDF-TO-EXCEL EXTRACTOR</p>
              </div>
            </Link>
            <Navigation />
          </div>
        </header>

        {/* Page Routing */}
        <ErrorBoundary>
          <Routes>
            <Route path="/home" element={<Home />} />
            <Route path="/history" element={<History />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/dashboard/:id" element={<Dashboard />} />
            
            {/* Default redirect to home */}
            <Route path="*" element={<Navigate to="/home" replace />} />
          </Routes>
        </ErrorBoundary>
      </div>
    </Router>
  );
}

export default App;
