import re

with open('frontend/src/App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add states
state_addition = """
  const [nearbySources, setNearbySources] = useState(null);
  const [loadingSources, setLoadingSources] = useState(false);
"""
if "const [nearbySources" not in content:
    content = re.sub(r'(const \[modalStation, setModalStation\] = useState\(null\);)', r'\1' + '\n' + state_addition, content)

# 2. Add fetch logic in openStationModal to clear previous sources
if "setNearbySources(null);" not in content:
    content = re.sub(r'(setExplainData\(null\);)', r'\1\n    setNearbySources(null);', content)

# 3. Add effect to fetch sources when tab is active
effect_addition = """
  // Fetch nearby sources when the 'sources' tab is opened
  useEffect(() => {
    if (activeTab === 'sources' && modalStation && !nearbySources && !loadingSources) {
      setLoadingSources(true);
      fetch(`${API_BASE}/nearby-sources/${encodeURIComponent(modalStation.name)}`)
        .then(res => res.json())
        .then(data => {
          setNearbySources(data);
          setLoadingSources(false);
        })
        .catch(err => {
          console.error("Failed to fetch sources", err);
          setNearbySources({ sources: [], message: "Failed to fetch nearby sources." });
          setLoadingSources(false);
        });
    }
  }, [activeTab, modalStation, nearbySources, loadingSources]);
"""
if "Fetch nearby sources when" not in content:
    content = re.sub(r'(const openStationModal = async \(station\) => \{)', effect_addition + r'\n  \1', content)

# 4. Add the tab button
import_icons_addition = ""
if "MapPin" not in content:
    content = re.sub(r'import \{\s*([^}]*?)\s*\} from \'lucide-react\';', r'import { \1, MapPin } from \'lucide-react\';', content)

tab_addition = """
              <button 
                onClick={() => setActiveTab('sources')}
                className={`pb-3 border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeTab === 'sources' ? 'border-cyan-500 text-cyan-400' : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}>
                <MapPin className="w-3.5 h-3.5 text-rose-400" />
                <span>Nearby Sources</span>
              </button>
"""
if "Nearby Sources</span>" not in content:
    content = re.sub(r'(<button\s*onClick=\{.*?setActiveTab\(\'explain\'\).*?</button>)', r'\1' + tab_addition, content, flags=re.DOTALL)

# 5. Add the tab body
body_addition = """
              ) : activeTab === 'sources' ? (
                <div className="space-y-4">
                  <div className="p-4 bg-gradient-to-r from-slate-950 via-[#0F172A] to-rose-950/20 border border-rose-500/20 rounded-xl shadow-lg">
                    <div className="flex items-center gap-2 mb-1.5">
                      <MapPin className="w-4 h-4 text-rose-400" />
                      <span className="text-xs font-bold text-rose-300 uppercase tracking-wider">Local Industrial Activity</span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      Real OpenStreetMap-tagged industrial activity within 7km — coverage may be incomplete and this is not an official regulatory source list.
                    </p>
                  </div>
                  
                  {loadingSources ? (
                    <div className="py-12 text-center text-xs text-slate-500">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-rose-500" />
                      Querying Overpass API for real OSM features...
                    </div>
                  ) : nearbySources && nearbySources.sources.length > 0 ? (
                    <div className="space-y-2">
                      {nearbySources.sources.map((src, i) => (
                        <div key={i} className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg flex items-center justify-between">
                          <div>
                            <div className="text-sm font-bold text-white">{src.name}</div>
                            <div className="text-xs text-slate-400">{src.type}</div>
                          </div>
                          <div className="text-sm font-mono text-cyan-300 bg-cyan-950/50 px-2 py-1 rounded border border-cyan-500/30">
                            {src.distance_km} km
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-8 text-center text-slate-500 text-sm">
                      {nearbySources?.message || "No tagged industrial sources found within 7km."}
                    </div>
                  )}
                </div>
"""
if "activeTab === 'sources'" not in content:
    content = re.sub(r'(\) : \(\s*/\*\s*"Why is pollution changing\?"\s*SHAP)', body_addition + r'\n              \1', content)

with open('frontend/src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("App.jsx updated with nearby sources tab.")
