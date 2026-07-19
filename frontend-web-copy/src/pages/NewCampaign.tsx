import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Title, Text } from '@tremor/react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Send, Sparkles, Loader2, Bot } from 'lucide-react';

export default function NewCampaign() {
  const navigate = useNavigate();
  const [error, setError] = useState('');
  
  const [chatInput, setChatInput] = useState('');
  const [isParsing, setIsParsing] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [foundLeads, setFoundLeads] = useState<any[]>([]);
  
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    target_criteria: '',
    location: '',
    niche: '',
    max_leads_per_day: 100
  });

  const downloadCSV = () => {
    if (foundLeads.length === 0) return;
    const headers = ["Name", "Technology", "University", "Visa", "Graduation Year", "Email", "Contact", "Summary", "LinkedIn"];
    const rows = foundLeads.map(l => [
      l.name || l.candidate_name || 'N/A',
      l.technology || 'N/A',
      l.university || 'N/A',
      l.visa || 'N/A',
      l.graduation_year || 'N/A',
      l.email || 'N/A',
      l.contact || 'N/A',
      // Escape quotes and remove newlines in summary to prevent CSV breakage
      (l.summary || 'N/A').replace(/"/g, '""').replace(/\n/g, ' '),
      l.linkedin_url || 'N/A'
    ]);
    
    const csvContent = "data:text/csv;charset=utf-8," 
      + headers.join(",") + "\n"
      + rows.map(r => r.map(c => `"${c}"`).join(",")).join("\n");
      
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "campaign_results.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // --- LOCAL PYTHON SCRAPER TRIGGER FUNCTION ---
  const triggerPythonScraper = async (targetLeads: number = 40) => {
    try {
      console.log(`Triggering local python scraper for ${targetLeads} leads...`);
      const response = await fetch('http://127.0.0.1:5000/start-campaign', {
        method: 'POST',
        headers: {
          'Content-Type': 'text/plain',
        },
        body: JSON.stringify({ 
          target_leads: targetLeads,
          niche: formData.niche || 'Computer Science',
          location: formData.location || 'US'
        }),
      });

      if (!response.ok) {
        throw new Error("Local scraper service is not responding.");
      }

      const data = await response.json();
      if (data.status === 'success') {
        console.log("🚀 Success: Local Python Scraper has started in background!");
        return true;
      }
    } catch (err: any) {
      console.warn("⚠️ Local Scraper warning:", err.message);
      throw err;
    }
    return false;
  };

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    
    setIsParsing(true);
    setError('');
    
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/campaigns/parse-prompt`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ prompt: chatInput })
      });
      
      if (res.ok) {
        const data = await res.json();
        setFormData({
          target_criteria: data.target_criteria || chatInput,
          location: data.location || '',
          niche: data.niche || '',
          max_leads_per_day: data.max_leads_per_day || 100
        });
        setShowForm(true);
      } else {
        // Fallback parsing if main backend is down
        setFormData({
          target_criteria: chatInput,
          location: 'US',
          niche: 'Computer Science',
          max_leads_per_day: 20
        });
        setShowForm(true);
      }
    } catch (err: any) {
      // Direct Fallback so the UI doesn't block the user
      setFormData({
        target_criteria: chatInput,
        location: 'US',
        niche: 'Computer Science',
        max_leads_per_day: 20
      });
      setShowForm(true);
    } finally {
      setIsParsing(false);
    }
  };

  const handleLaunchCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsProcessing(true);
    setError('');

    try {
      const token = localStorage.getItem('auth_token');
      await new Promise(resolve => setTimeout(resolve, 1500));

      let threadId = "local_" + Date.now().toString().slice(-5);
      const leadsToScrape = formData.max_leads_per_day || 20;

      try {
        // Attempting to notify main backend
        const startRes = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/campaigns/start`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(formData)
        });

        if (startRes.ok) {
          const startData = await startRes.json();
          threadId = startData.thread_id || threadId;
        }
      } catch (backendErr) {
        console.warn("⚠️ Main backend is offline. Running campaign in offline/local-only mode.");
      }

      // Get baseline leads before starting
      let initialLeads = 0;
      try {
        const baselineRes = await fetch('http://127.0.0.1:5000/api/dashboard/');
        if (baselineRes.ok) {
           const baselineData = await baselineRes.json();
           initialLeads = baselineData.stats?.total_leads || 0;
        }
      } catch (e) {}

      // Main Scraper Execution
      await triggerPythonScraper(leadsToScrape);
      
      // Dynamic Polling: Wait up to 2 minutes (120,000 ms) for results to appear
      const startTime = Date.now();
      const MAX_WAIT_MS = 120 * 1000;
      
      while (Date.now() - startTime < MAX_WAIT_MS) {
         // Poll every 3 seconds
         await new Promise(resolve => setTimeout(resolve, 3000)); 
         try {
            const checkRes = await fetch('http://127.0.0.1:5000/api/dashboard/');
            if (checkRes.ok) {
               const checkData = await checkRes.json();
               const currentLeads = checkData.stats?.total_leads || 0;
               // If leads have increased, we found NEW leads! Break the loop early!
               if (currentLeads > initialLeads) {
                  const new_count = currentLeads - initialLeads;
                  setFoundLeads((checkData.recent_leads || []).slice(0, new_count));
                  break;
               }
            }
         } catch (e) {
            // Ignore temporary fetch errors while backend might be busy
         }
      }

      const addNotification = (title: string, msg: string) => {
        const existing = JSON.parse(localStorage.getItem('crm_notifications') || '[]');
        const newNotif = {
          id: Date.now().toString() + Math.random(),
          title,
          message: msg,
          date: new Date().toISOString(),
          read: false
        };
        localStorage.setItem('crm_notifications', JSON.stringify([newNotif, ...existing]));
        window.dispatchEvent(new Event('notificationsUpdated'));
      };

      addNotification('Campaign Started', 'Your intelligent outreach campaign has been initiated.');
      
      setTimeout(() => {
        addNotification('Leads Found', `AI Agent found leads for campaign ${threadId.substring(0, 5)}.`);
      }, 5000);

      // Stop the animation but STAY on the page to show the results
      setIsProcessing(false);

    } catch (err: any) {
      setError("Could not start scraper. Please make sure python script is running on port 5000.");
      setIsProcessing(false);
    }
  };

  if (isProcessing) {
    return (
      <div className="fixed inset-0 z-50 bg-white/80 backdrop-blur-md flex flex-col items-center justify-center text-slate-900 overflow-hidden">
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="relative z-10 flex flex-col items-center"
        >
          <div className="relative mb-8">
            <motion.div 
              animate={{ scale: [1, 1.1, 1], opacity: [0.8, 1, 0.8] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
              className="w-16 h-16 rounded-full bg-slate-900 flex items-center justify-center text-white shadow-xl"
            >
              <Sparkles className="w-8 h-8" />
            </motion.div>
          </div>
          
          <h2 className="text-2xl font-bold mb-3 tracking-tight">Orchestrating Campaign</h2>
          <div className="text-sm text-slate-500 max-w-md text-center h-20">
            <AnimatePresence mode="wait">
              <motion.div
                key="text1"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="mb-1"
              >
                Synthesizing target profile...
              </motion.div>
              <motion.div
                key="text2"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.8 }}
                className="mb-1"
              >
                Connecting data streams...
              </motion.div>
              <motion.div
                key="text3"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.5 }}
              >
                Launching intelligent outreach...
              </motion.div>
            </AnimatePresence>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-10 max-w-4xl mx-auto">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <button 
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-2 text-slate-500 hover:text-slate-900 transition-colors mb-6 text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </button>

        <div className="mb-8">
          <Title className="text-3xl text-slate-900 font-bold">New Campaign</Title>
          <Text className="text-slate-500 mt-1">Configure your target audience and let our AI engine find leads.</Text>
        </div>

        {error && (
          <div className="bg-red-50 text-red-600 p-4 rounded-xl mb-6 text-sm max-w-2xl mx-auto">
            {error}
          </div>
        )}

        {!showForm ? (
          <div className="max-w-2xl mx-auto mt-12">
            <form onSubmit={handleChatSubmit} className="relative z-10">
              <div className="relative flex items-center shadow-lg rounded-2xl bg-white ring-1 ring-slate-100">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Describe your ideal customer... e.g., 'Find me 50 AI founders in SF'"
                  className="w-full h-16 pl-6 pr-36 rounded-2xl border-none bg-transparent text-base focus:outline-none focus:ring-2 focus:ring-slate-900 transition-all"
                  disabled={isParsing}
                />
                <button
                  type="submit"
                  disabled={isParsing || !chatInput.trim()}
                  className="absolute right-2 h-12 px-6 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-900/50 text-white rounded-xl text-sm font-semibold transition-colors flex items-center gap-2"
                >
                  {isParsing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  Auto-Fill Form
                </button>
              </div>
            </form>
            <div className="flex justify-between items-center mt-4 px-2">
              <p className="text-slate-400 text-sm">
                Press Enter to let AI configure your campaign settings.
              </p>
              <button 
                onClick={() => setShowForm(true)}
                className="text-indigo-600 hover:text-indigo-700 text-sm font-medium transition-colors"
              >
                Or fill out form manually
              </button>
            </div>
          </div>
        ) : (foundLeads.length === 0 && !isProcessing) ? (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-2xl mx-auto mt-8 bg-white p-8 rounded-2xl shadow-sm border border-slate-100"
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                <Bot className="w-5 h-5 text-indigo-600" />
                Campaign Configuration
              </h3>
              <button 
                type="button"
                onClick={() => setShowForm(false)}
                className="text-sm text-slate-500 hover:text-slate-700 font-medium"
              >
                Use AI Prompt Instead
              </button>
            </div>
            
            <form onSubmit={handleLaunchCampaign} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Target Audience / Criteria</label>
                <input 
                  type="text" 
                  value={formData.target_criteria}
                  onChange={e => setFormData({...formData, target_criteria: e.target.value})}
                  placeholder="e.g., Senior Secondary Schools"
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-indigo-600/20 focus:border-indigo-600 outline-none transition-all text-sm"
                  required
                />
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Location</label>
                  <input 
                    type="text" 
                    value={formData.location}
                    onChange={e => setFormData({...formData, location: e.target.value})}
                    placeholder="e.g., Bharatpur, India"
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-indigo-600/20 focus:border-indigo-600 outline-none transition-all text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Specific Niche (Optional)</label>
                  <input 
                    type="text" 
                    value={formData.niche}
                    onChange={e => setFormData({...formData, niche: e.target.value})}
                    placeholder="e.g., EdTech startups"
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-indigo-600/20 focus:border-indigo-600 outline-none transition-all text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Max Leads to Find</label>
                <input 
                  type="number" 
                  value={formData.max_leads_per_day}
                  onChange={e => setFormData({...formData, max_leads_per_day: parseInt(e.target.value) || 20})}
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-indigo-600/20 focus:border-indigo-600 outline-none transition-all text-sm"
                  min="1"
                  max="1000"
                />
              </div>
              
              <div className="pt-4 border-t border-slate-100 mt-6 flex justify-end">
                <button
                  type="submit"
                  disabled={!formData.target_criteria.trim() || isProcessing}
                  className="h-12 px-8 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-600/50 text-white rounded-xl text-sm font-bold transition-colors shadow-lg shadow-indigo-600/20 flex items-center gap-2"
                >
                  <Send className="w-4 h-4" />
                  Launch Campaign
                </button>
              </div>
            </form>
          </motion.div>
        ) : null}

        {foundLeads.length > 0 && !isProcessing && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-4xl mx-auto mt-8 bg-white p-8 rounded-2xl shadow-sm border border-slate-100"
          >
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-slate-900 flex items-center gap-2 mb-1">
                  <Sparkles className="w-5 h-5 text-emerald-600" />
                  Campaign Results
                </h3>
                <p className="text-sm text-slate-500">Here are the fresh leads we just extracted based on your criteria:</p>
              </div>
              <button 
                onClick={downloadCSV}
                className="h-10 px-4 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-lg text-sm font-semibold transition-colors flex items-center gap-2"
              >
                Download CSV
              </button>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <th className="py-3 px-4">Name</th>
                    <th className="py-3 px-4">Tech/Role</th>
                    <th className="py-3 px-4">University</th>
                    <th className="py-3 px-4">Visa</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {foundLeads.map((lead, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                      <td className="py-4 px-4 text-sm font-medium text-slate-900">{lead.name || lead.candidate_name || 'Unknown'}</td>
                      <td className="py-4 px-4 text-sm text-slate-600 truncate max-w-[150px]">{lead.technology || '-'}</td>
                      <td className="py-4 px-4 text-sm text-slate-600">{lead.university || '-'}</td>
                      <td className="py-4 px-4 text-sm text-slate-600">
                        <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-md text-xs font-medium">
                          {lead.visa || 'Unknown'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mt-4 pt-4 border-t border-slate-100 flex justify-between items-center">
                <button 
                  onClick={() => {
                    setFoundLeads([]);
                    setShowForm(false);
                    setChatInput('');
                  }}
                  className="text-slate-500 hover:text-slate-700 text-sm font-medium transition-colors"
                >
                  Start New Campaign
                </button>
                <button 
                  onClick={() => navigate('/dashboard/leads')}
                  className="text-indigo-600 hover:text-indigo-700 text-sm font-medium transition-colors"
                >
                  View in Campaign History &rarr;
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}