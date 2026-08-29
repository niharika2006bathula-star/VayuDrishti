import re

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add 'simulator' to the comment for navTab
content = content.replace(
    "const [navTab, setNavTab] = useState('dashboard'); // 'dashboard' | 'stations' | 'alerts' | 'settings'",
    "const [navTab, setNavTab] = useState('dashboard'); // 'dashboard' | 'stations' | 'alerts' | 'settings' | 'simulator'"
)

# 2. Add state variables for the Simulator
state_code = '''
  // Simulator State
  const [simPm25, setSimPm25] = useState(250);
  const [simWindSpeed, setSimWindSpeed] = useState(1.0);
  const [simWindDir, setSimWindDir] = useState(270);
  const [simTemp, setSimTemp] = useState(12);
  const [simHumidity, setSimHumidity] = useState(85);
  const [simPbl, setSimPbl] = useState(300);
  const [simPrecip, setSimPrecip] = useState(0);
  const [simFeedback, setSimFeedback] = useState(true);
  const [simResults, setSimResults] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simError, setSimError] = useState(null);

  const loadSevereWinterScenario = () => {
    setSimPm25(250);
    setSimWindSpeed(1.0);
    setSimWindDir(270);
    setSimTemp(12);
    setSimHumidity(85);
    setSimPbl(300);
    setSimPrecip(0);
    setSimFeedback(true);
  };

  const runSimulation = async () => {
    setIsSimulating(true);
    setSimError(null);
    try {
      const res = await fetch("http://localhost:8000/simulate", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pm25: simPm25,
          wind_speed: simWindSpeed,
          wind_direction: simWindDir,
          temperature: simTemp,
          humidity: simHumidity,
          pbl: simPbl,
          precipitation: simPrecip,
          enable_feedback: simFeedback
        })
      });
      if (!res.ok) throw new Error('Simulation failed');
      const data = await res.json();
      setSimResults(data);
    } catch (e) {
      setSimError(e.message);
    } finally {
      setIsSimulating(false);
    }
  };

  const [alertsData, setAlertsData] = useState(null);
'''
content = content.replace(
    "  const [alertsData, setAlertsData] = useState(null);",
    state_code
)

# 3. Add Sidebar Nav Item
nav_item_code = '''
            <button 
              onClick={() => setNavTab('simulator')}
              className={`w-full flex items-center gap-3 px-4 py-3 border-l-4 transition-all ${
                navTab === 'simulator' ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500' : 'border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}>
              <Play className="w-5 h-5" />
              <div className="flex flex-col items-start">
                <span className="font-semibold text-sm">Scenario Simulator</span>
                <span className="text-[10px] opacity-70">Hypothetical Forecasts</span>
              </div>
            </button>
            <button 
              onClick={() => setNavTab('settings')}
'''
content = content.replace(
    "            <button \n              onClick={() => setNavTab('settings')}",
    nav_item_code
)

# 4. Add header title
title_code = '''
              {navTab === 'simulator' && 'Scenario Simulator (What-If Forecasting)'}
              {navTab === 'settings' && 'System Configuration & Machine Learning Metadata'}
'''
content = content.replace(
    "              {navTab === 'settings' && 'System Configuration & Machine Learning Metadata'}",
    title_code
)

# 5. Add Simulator Page component code
page_code = '''
          {navTab === 'simulator' && (
            <div className="animate-in fade-in zoom-in-95 duration-300">
              <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-6 shadow-xl mb-6">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h2 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
                      <Play className="w-5 h-5 text-cyan-400" /> Scenario Simulator
                    </h2>
                    <p className="text-sm text-slate-400">Test hypothetical pollution scenarios by overriding weather inputs into the autoregressive XGBoost model.</p>
                  </div>
                  <button 
                    onClick={loadSevereWinterScenario}
                    className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-semibold rounded-lg border border-slate-700 transition-colors flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" /> Load Severe Winter Scenario
                  </button>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  {/* Left Column: Inputs */}
                  <div className="space-y-5">
                    <div>
                      <div className="flex justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-300">Starting PM2.5 (µg/m³)</label>
                        <span className="text-xs text-cyan-400 font-bold">{simPm25}</span>
                      </div>
                      <input type="range" min="0" max="400" value={simPm25} onChange={e => setSimPm25(Number(e.target.value))} className="w-full accent-cyan-500" />
                    </div>
                    <div>
                      <div className="flex justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-300">Wind Speed (m/s)</label>
                        <span className="text-xs text-cyan-400 font-bold">{simWindSpeed}</span>
                      </div>
                      <input type="range" min="0" max="15" step="0.1" value={simWindSpeed} onChange={e => setSimWindSpeed(Number(e.target.value))} className="w-full accent-cyan-500" />
                    </div>
                    <div>
                      <div className="flex justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-300">Wind Direction (°)</label>
                        <span className="text-xs text-cyan-400 font-bold">{simWindDir}°</span>
                      </div>
                      <input type="range" min="0" max="360" value={simWindDir} onChange={e => setSimWindDir(Number(e.target.value))} className="w-full accent-cyan-500" />
                    </div>
                    <div>
                      <div className="flex justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-300">Temperature (°C)</label>
                        <span className="text-xs text-cyan-400 font-bold">{simTemp}</span>
                      </div>
                      <input type="range" min="-5" max="45" value={simTemp} onChange={e => setSimTemp(Number(e.target.value))} className="w-full accent-cyan-500" />
                    </div>
                    <div>
                      <div className="flex justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-300">Humidity (%)</label>
                        <span className="text-xs text-cyan-400 font-bold">{simHumidity}</span>
                      </div>
                      <input type="range" min="0" max="100" value={simHumidity} onChange={e => setSimHumidity(Number(e.target.value))} className="w-full accent-cyan-500" />
                    </div>
                    <div>
                      <div className="flex justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-300">PBL Height (m)</label>
                        <span className="text-xs text-cyan-400 font-bold">{simPbl}</span>
                      </div>
                      <input type="range" min="50" max="2000" step="10" value={simPbl} onChange={e => setSimPbl(Number(e.target.value))} className="w-full accent-cyan-500" />
                    </div>
                    <div>
                      <div className="flex justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-300">Precipitation (mm)</label>
                        <span className="text-xs text-cyan-400 font-bold">{simPrecip}</span>
                      </div>
                      <input type="range" min="0" max="20" step="0.1" value={simPrecip} onChange={e => setSimPrecip(Number(e.target.value))} className="w-full accent-cyan-500" />
                    </div>
                    
                    <div className="flex items-center justify-between p-3 bg-slate-900 border border-slate-800 rounded-lg">
                      <span className="text-sm font-semibold text-slate-300">Enable Aerosol-PBL Feedback</span>
                      <button 
                        onClick={() => setSimFeedback(!simFeedback)}
                        className={`w-11 h-6 rounded-full transition-colors relative ${simFeedback ? 'bg-cyan-500' : 'bg-slate-700'}`}>
                        <span className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-all ${simFeedback ? 'left-6' : 'left-1'}`} />
                      </button>
                    </div>

                    <button 
                      onClick={runSimulation}
                      disabled={isSimulating}
                      className="w-full py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-bold rounded-lg transition-colors flex items-center justify-center gap-2">
                      {isSimulating ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                      {isSimulating ? 'Simulating...' : 'Run Simulation'}
                    </button>
                    
                    {simError && <div className="text-red-400 text-sm mt-2 p-2 bg-red-950/50 rounded border border-red-900/50">{simError}</div>}
                  </div>

                  {/* Right Column: Output Chart */}
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col h-full min-h-[400px]">
                    <h3 className="text-sm font-bold text-white mb-4">Simulation Results (24 Hours)</h3>
                    {!simResults ? (
                      <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
                        <Activity className="w-12 h-12 mb-3 opacity-20" />
                        <p className="text-sm">Run a simulation to view forecasts.</p>
                      </div>
                    ) : (
                      <div className="flex-1 flex flex-col">
                        <div className="flex-1 relative mb-6 border-b border-l border-slate-700">
                          {/* SVG Chart */}
                          <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                            {/* Baseline Line */}
                            <path 
                              d={`M ${simResults.baseline_forecast.map((val, i) => `${(i / 23) * 100} ${100 - (Math.min(val, 400) / 400) * 100}`).join(' L ')}`} 
                              fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="4 4" 
                            />
                            {/* Feedback Line */}
                            <path 
                              d={`M ${simResults.feedback_forecast.map((val, i) => `${(i / 23) * 100} ${100 - (Math.min(val, 400) / 400) * 100}`).join(' L ')}`} 
                              fill="none" stroke="#f43f5e" strokeWidth="2" 
                            />
                          </svg>
                          
                          {/* Y-Axis Labels */}
                          <div className="absolute top-0 -left-8 text-[10px] text-slate-500">400</div>
                          <div className="absolute top-1/2 -left-8 text-[10px] text-slate-500 -translate-y-1/2">200</div>
                          <div className="absolute bottom-0 -left-6 text-[10px] text-slate-500 translate-y-1/2">0</div>
                          
                          {/* X-Axis Labels */}
                          <div className="absolute -bottom-6 left-0 text-[10px] text-slate-500">Hr 1</div>
                          <div className="absolute -bottom-6 right-0 text-[10px] text-slate-500">Hr 24</div>
                        </div>

                        <div className="flex items-center gap-6 text-xs mb-4">
                          <div className="flex items-center gap-2">
                            <div className="w-4 border-t-2 border-dashed border-slate-400"></div>
                            <span className="text-slate-300">Baseline Forecast</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="w-4 border-t-2 border-rose-500"></div>
                            <span className="text-rose-300 font-semibold">Feedback Forecast</span>
                          </div>
                        </div>
                        
                        <div className="mt-auto pt-4 border-t border-slate-800 space-y-3">
                          <p className="text-[11px] text-slate-400 italic">
                            Illustrative scenario testing based on published aerosol-PBL feedback research — not live production data. Our current dataset covers a low-pollution season where this mechanism rarely activates in real forecasts.
                          </p>
                          <p className="text-[11px] text-slate-400 italic">
                            Note: the feedback effect is measurable but brief in this simulation (visible mainly in hour 1) because our model is trained on non-winter data and predicts pollution levels reverting quickly, even under simulated stagnant conditions. This itself illustrates a real limitation of training on a low-pollution season.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
          {navTab === 'settings' && (
'''
content = content.replace(
    "          {navTab === 'settings' && (",
    page_code
)

with open('src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
