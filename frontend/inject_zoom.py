import os

# The useSvgZoomPan hook code
hook_code = """
const useSvgZoomPan = (initialWidth, initialHeight) => {
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: initialWidth, h: initialHeight });
  const [isZoomed, setIsZoomed] = useState(false);
  const [dragState, setDragState] = useState(null);
  const svgRef = useRef(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    
    const handleWheel = (e) => {
      e.preventDefault();
      
      const pt = svg.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      const svgPt = pt.matrixTransform(svg.getScreenCTM().inverse());
      
      const scale = e.deltaY > 0 ? 1.15 : 0.85;
      
      setViewBox(prev => {
        let newW = prev.w * scale;
        let newH = prev.h * scale;
        
        if (newW > initialWidth) {
          newW = initialWidth;
          newH = initialHeight;
        }
        
        let newX = svgPt.x - (svgPt.x - prev.x) * scale;
        let newY = svgPt.y - (svgPt.y - prev.y) * scale;
        
        if (newW >= initialWidth - 1) {
          newX = 0;
          newY = 0;
          newW = initialWidth;
          newH = initialHeight;
        }
        
        setIsZoomed(newW < initialWidth - 1);
        return { x: newX, y: newY, w: newW, h: newH };
      });
    };
    
    svg.addEventListener('wheel', handleWheel, { passive: false });
    return () => svg.removeEventListener('wheel', handleWheel);
  }, [initialWidth, initialHeight]);

  const getSvgPoint = (e) => {
    if (!svgRef.current) return { x: 0, y: 0 };
    const pt = svgRef.current.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    return pt.matrixTransform(svgRef.current.getScreenCTM().inverse());
  };

  const handleMouseDown = (e) => {
    const pt = getSvgPoint(e);
    const mode = (e.shiftKey || isZoomed) ? 'pan' : 'zoom';
    setDragState({ startX: pt.x, startY: pt.y, currentX: pt.x, currentY: pt.y, mode });
  };

  const handleMouseMove = (e) => {
    if (!dragState) return;
    const pt = getSvgPoint(e);
    
    if (dragState.mode === 'pan') {
      const dx = pt.x - dragState.currentX;
      const dy = pt.y - dragState.currentY;
      setViewBox(prev => ({ ...prev, x: prev.x - dx, y: prev.y - dy }));
      setDragState(prev => ({ ...prev, currentX: pt.x - dx, currentY: pt.y - dy }));
    } else {
      setDragState(prev => ({ ...prev, currentX: pt.x, currentY: pt.y }));
    }
  };

  const handleMouseUp = () => {
    if (!dragState) return;
    if (dragState.mode === 'zoom') {
      const minX = Math.min(dragState.startX, dragState.currentX);
      const minY = Math.min(dragState.startY, dragState.currentY);
      const w = Math.abs(dragState.currentX - dragState.startX);
      const h = Math.abs(dragState.currentY - dragState.startY);
      
      if (w > 10 && h > 10) {
        setViewBox({ x: minX, y: minY, w: w, h: h });
        setIsZoomed(true);
      }
    }
    setDragState(null);
  };

  const resetZoom = () => {
    setViewBox({ x: 0, y: 0, w: initialWidth, h: initialHeight });
    setIsZoomed(false);
  };

  return {
    svgRef,
    viewBoxStr: `${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`,
    isZoomed,
    dragState,
    resetZoom,
    getSvgPoint,
    handlers: {
      onMouseDown: handleMouseDown,
      onMouseMove: handleMouseMove,
      onMouseUp: handleMouseUp,
      onMouseLeave: handleMouseUp,
    }
  };
};
"""

# The MultiLineTrendChart code
multi_line_code = """
function MultiLineTrendChart({ historyData, days, onDaysChange, stationName, onOpenModal }) {
  const [hoverIndex, setHoverIndex] = useState(null);
  const width = 800;
  const height = 210;
  const zoomPan = useSvgZoomPan(width, height);

  if (!historyData || historyData.length === 0) {
    return (
      <div className="h-60 flex items-center justify-center text-slate-500 text-xs bg-slate-900/40 rounded-2xl border border-slate-800">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-cyan-500" />
        Loading real historical telemetry for {stationName}...
      </div>
    );
  }

  const padLeft = 45;
  const padRight = 45;
  const padTop = 18;
  const padBottom = 28;

  const innerWidth = width - padLeft - padRight;
  const innerHeight = height - padTop - padBottom;

  const pmValues = historyData.map(d => d.pm25);
  const tempValues = historyData.map(d => d.temperature);

  const minPm = 0;
  const maxPm = Math.max(80, Math.ceil(Math.max(...pmValues) / 20) * 20);

  const minTemp = Math.floor(Math.min(...tempValues) - 2);
  const maxTemp = Math.ceil(Math.max(...tempValues) + 2);

  const getX = (i) => padLeft + (i / (historyData.length - 1)) * innerWidth;
  const getYPm = (val) => padTop + innerHeight - ((val - minPm) / (maxPm - minPm)) * innerHeight;
  const getYTemp = (val) => padTop + innerHeight - ((val - minTemp) / (maxTemp - minTemp)) * innerHeight;

  // Build SVG Path Strings
  const pmPath = historyData.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i).toFixed(1)} ${getYPm(d.pm25).toFixed(1)}`).join(' ');
  const tempPath = historyData.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i).toFixed(1)} ${getYTemp(d.temperature).toFixed(1)}`).join(' ');

  const pmAreaPath = `${pmPath} L ${getX(historyData.length - 1)} ${padTop + innerHeight} L ${padLeft} ${padTop + innerHeight} Z`;
  const hoveredPoint = hoverIndex !== null ? historyData[hoverIndex] : null;

  return (
    <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur-md">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-sm text-white font-heading flex items-center gap-2">
              <span>Historical Trend: <span className="text-cyan-400">{stationName}</span></span>
            </h3>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-950/70 text-cyan-300 border border-cyan-500/30 font-medium">
              Real Historical Telemetry
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Station PM2.5 vs. Regional Ambient Temperature (Hourly resolution)
          </p>
        </div>

        <div className="flex items-center gap-3.5">
          <div className="flex items-center gap-3 text-xs font-semibold">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-sm shadow-cyan-500/50"></span>
              <span className="text-cyan-300">PM2.5 (µg/m³)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shadow-sm shadow-rose-500/50"></span>
              <span className="text-rose-300">Temperature (°C)</span>
            </div>
          </div>

          <div className="flex items-center bg-slate-950 border border-slate-800 rounded-lg p-0.5 text-xs">
            <button
              onClick={() => onDaysChange(7)}
              className={`px-2.5 py-1 rounded-md transition-all font-semibold ${
                days === 7 ? 'bg-cyan-500 text-slate-950 shadow-md' : 'text-slate-400 hover:text-slate-200'
              }`}>
              7 Days
            </button>
            <button
              onClick={() => onDaysChange(30)}
              className={`px-2.5 py-1 rounded-md transition-all font-semibold ${
                days === 30 ? 'bg-cyan-500 text-slate-950 shadow-md' : 'text-slate-400 hover:text-slate-200'
              }`}>
              30 Days
            </button>
          </div>

          <button
            onClick={onOpenModal}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-all">
            <ExternalLink className="w-3 h-3 text-cyan-400" />
            <span className="hidden sm:inline">Inspect AI Details</span>
          </button>
        </div>
      </div>

      <div className="relative w-full overflow-hidden select-none">
        {zoomPan.isZoomed && (
          <button 
            onClick={zoomPan.resetZoom}
            className="absolute top-2 right-2 z-10 px-2 py-1 bg-slate-800/80 hover:bg-slate-700 text-xs text-white rounded border border-slate-600 backdrop-blur-sm shadow-lg flex items-center gap-1 transition-all"
          >
            <RefreshCw className="w-3 h-3" /> Reset Zoom
          </button>
        )}
        <svg 
          ref={zoomPan.svgRef}
          viewBox={zoomPan.viewBoxStr} 
          className={`w-full h-auto overflow-visible ${zoomPan.isZoomed ? (zoomPan.dragState?.mode === 'pan' ? 'cursor-grabbing' : 'cursor-grab') : 'cursor-crosshair'}`}
          onMouseDown={zoomPan.handlers.onMouseDown}
          onMouseMove={(e) => {
            zoomPan.handlers.onMouseMove(e);
            if (!zoomPan.dragState) {
              const svgPt = zoomPan.getSvgPoint(e);
              if (svgPt.x >= padLeft && svgPt.x <= width - padRight) {
                 const i = Math.round(((svgPt.x - padLeft) / innerWidth) * (historyData.length - 1));
                 setHoverIndex(Math.max(0, Math.min(i, historyData.length - 1)));
              } else {
                 setHoverIndex(null);
              }
            }
          }}
          onMouseUp={zoomPan.handlers.onMouseUp}
          onMouseLeave={(e) => {
            zoomPan.handlers.onMouseLeave(e);
            setHoverIndex(null);
          }}>
          <defs>
            <linearGradient id="pmGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.20" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
            </linearGradient>
            <clipPath id="chartClip">
               <rect x={padLeft} y={0} width={innerWidth} height={height} />
            </clipPath>
          </defs>

          {/* Gridlines with 0.5px strokeWidth */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio, idx) => {
            const y = padTop + innerHeight * ratio;
            const pmVal = Math.round(maxPm - ratio * (maxPm - minPm));
            const tempVal = (maxTemp - ratio * (maxTemp - minTemp)).toFixed(1);
            return (
              <g key={idx}>
                <line x1={padLeft} y1={y} x2={width - padRight} y2={y} stroke="#1e293b" strokeWidth="0.5" strokeDasharray="3 3" />
                <text x={padLeft - 8} y={y + 3} fill="#64748b" fontSize="9" textAnchor="end" fontFamily="sans-serif">
                  {pmVal}
                </text>
                <text x={width - padRight + 8} y={y + 3} fill="#fda4af" fontSize="9" textAnchor="start" fontFamily="sans-serif">
                  {tempVal}°
                </text>
              </g>
            );
          })}

          <g clipPath="url(#chartClip)">
            <path d={pmAreaPath} fill="url(#pmGradient)" />
            {/* Trend lines with 1px strokeWidth */}
            <path d={tempPath} fill="none" stroke="#f43f5e" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
            <path d={pmPath} fill="none" stroke="#06b6d4" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />

            {/* Hover Indicator */}
            {hoverIndex !== null && !zoomPan.dragState && (
              <g>
                <line 
                  x1={getX(hoverIndex)} 
                  y1={padTop} 
                  x2={getX(hoverIndex)} 
                  y2={padTop + innerHeight} 
                  stroke="#334155" 
                  strokeWidth="1"
                  strokeDasharray="2 2" 
                />
                <circle cx={getX(hoverIndex)} cy={getYPm(historyData[hoverIndex].pm25)} r="3.5" fill="#06b6d4" stroke="#0F172A" strokeWidth="1.5" />
                <circle cx={getX(hoverIndex)} cy={getYTemp(historyData[hoverIndex].temperature)} r="3.5" fill="#f43f5e" stroke="#0F172A" strokeWidth="1.5" />
              </g>
            )}
          </g>

          {/* Draw zoom selection box */}
          {zoomPan.dragState && zoomPan.dragState.mode === 'zoom' && (
             <rect 
               x={Math.min(zoomPan.dragState.startX, zoomPan.dragState.currentX)}
               y={Math.min(zoomPan.dragState.startY, zoomPan.dragState.currentY)}
               width={Math.abs(zoomPan.dragState.currentX - zoomPan.dragState.startX)}
               height={Math.abs(zoomPan.dragState.currentY - zoomPan.dragState.startY)}
               fill="rgba(6, 182, 212, 0.15)"
               stroke="#06b6d4"
               strokeWidth="1"
               strokeDasharray="4 4"
             />
          )}
        </svg>

        {hoveredPoint && !zoomPan.dragState && (
          <div className="absolute top-2 left-[50%] -translate-x-[50%] bg-slate-800/90 border border-slate-700 p-2 rounded-lg text-[10px] shadow-lg backdrop-blur-md pointer-events-none flex gap-4 z-20">
            <div>
              <span className="text-slate-400 block mb-0.5">Time</span>
              <span className="text-white font-medium">{new Date(hoveredPoint.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">PM2.5</span>
              <span className="text-cyan-400 font-bold">{hoveredPoint.pm25.toFixed(1)}</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Temp</span>
              <span className="text-rose-400 font-bold">{hoveredPoint.temperature.toFixed(1)}°C</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
"""

# The ModelScatterPlot code
model_scatter_code = """
// Interactive Scatter Plot for Global Model Accuracy
function ModelScatterPlot({ data }) {
  const width = 800;
  const height = 300;
  const zoomPan = useSvgZoomPan(width, height);

  if (!data || data.length === 0) return null;
  const pad = 40;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  
  const maxVal = Math.max(
    ...data.map(d => Math.max(d.actual, d.predicted)), 300
  );
  
  const getX = (val) => pad + (val / maxVal) * innerW;
  const getY = (val) => height - pad - (val / maxVal) * innerH;

  return (
    <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl mb-6">
      <h3 className="text-white font-bold mb-2 text-sm flex items-center justify-between">
        Global Model Accuracy (Holdout Test Set)
        <span className="text-xs text-slate-400 font-normal px-2 py-1 bg-slate-800 rounded border border-slate-700">n = {data.length.toLocaleString()} sampled</span>
      </h3>
      <p className="text-[11px] text-slate-400 mb-4 leading-relaxed">
        Each point is one real prediction from the held-out test set (18,544 total). Points near the diagonal line are accurate; scatter increases at higher pollution levels, consistent with our documented model limitations.
      </p>
      <div className="relative w-full overflow-hidden border border-slate-800/60 rounded-xl bg-slate-950/50 pt-2 pb-1 pr-4 select-none">
        {zoomPan.isZoomed && (
          <button 
            onClick={zoomPan.resetZoom}
            className="absolute top-2 right-2 z-10 px-2 py-1 bg-slate-800/90 hover:bg-slate-700 text-xs text-white rounded border border-slate-600 backdrop-blur-sm shadow-lg flex items-center gap-1 transition-all"
          >
            <RefreshCw className="w-3 h-3" /> Reset Zoom
          </button>
        )}
        <svg 
          ref={zoomPan.svgRef}
          viewBox={zoomPan.viewBoxStr} 
          className={`w-full h-auto overflow-visible ${zoomPan.isZoomed ? (zoomPan.dragState?.mode === 'pan' ? 'cursor-grabbing' : 'cursor-grab') : 'cursor-crosshair'}`}
          onMouseDown={zoomPan.handlers.onMouseDown}
          onMouseMove={zoomPan.handlers.onMouseMove}
          onMouseUp={zoomPan.handlers.onMouseUp}
          onMouseLeave={zoomPan.handlers.onMouseLeave}>
          
          <defs>
             <clipPath id="scatterClip">
                <rect x={pad} y={0} width={innerW} height={height} />
             </clipPath>
          </defs>

          {/* Grid and Axes (Stroke width 0.5px) */}
          <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#334155" strokeWidth="0.5"/>
          <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="#334155" strokeWidth="0.5"/>
          
          {/* X and Y labels */}
          <text x={width / 2} y={height - 5} fill="#94a3b8" fontSize="12" textAnchor="middle" fontWeight="bold">Actual PM2.5 (µg/m³)</text>
          <text x={12} y={height / 2} fill="#94a3b8" fontSize="12" textAnchor="middle" transform={`rotate(-90 12,${height/2})`} fontWeight="bold">Predicted PM2.5</text>
          
          {/* Axis Ticks (0, 100, 200, max) */}
          {[0, 100, 200, Math.floor(maxVal/100)*100].map(val => (
             <g key={`x-${val}`}>
               <line x1={getX(val)} y1={height - pad} x2={getX(val)} y2={height - pad + 4} stroke="#64748b" strokeWidth="0.5" />
               <text x={getX(val)} y={height - pad + 14} fill="#64748b" fontSize="10" textAnchor="middle">{val}</text>
             </g>
          ))}
          {[100, 200, Math.floor(maxVal/100)*100].map(val => (
             <g key={`y-${val}`}>
               <line x1={pad - 4} y1={getY(val)} x2={pad} y2={getY(val)} stroke="#64748b" strokeWidth="0.5" />
               <text x={pad - 6} y={getY(val) + 3} fill="#64748b" fontSize="10" textAnchor="end">{val}</text>
             </g>
          ))}

          <g clipPath="url(#scatterClip)">
            {/* Diagonal Perfect Prediction Line */}
            <line x1={getX(0)} y1={getY(0)} x2={getX(maxVal)} y2={getY(maxVal)} stroke="#cbd5e1" strokeDasharray="4 4" strokeWidth="1" opacity="0.6"/>
            
            {/* Data Points with reduced radiuses */}
            {data.map((d, i) => (
              <circle 
                key={i} 
                cx={getX(d.actual)} 
                cy={getY(d.predicted)} 
                r={d.actual > 200 ? 2.5 : 1.5} 
                fill={d.actual > 200 ? "#f43f5e" : "#0ea5e9"} 
                opacity={d.actual > 200 ? 0.8 : 0.5} 
              />
            ))}
          </g>

          {/* Draw zoom selection box */}
          {zoomPan.dragState && zoomPan.dragState.mode === 'zoom' && (
             <rect 
               x={Math.min(zoomPan.dragState.startX, zoomPan.dragState.currentX)}
               y={Math.min(zoomPan.dragState.startY, zoomPan.dragState.currentY)}
               width={Math.abs(zoomPan.dragState.currentX - zoomPan.dragState.startX)}
               height={Math.abs(zoomPan.dragState.currentY - zoomPan.dragState.startY)}
               fill="rgba(244, 63, 94, 0.15)"
               stroke="#f43f5e"
               strokeWidth="1"
               strokeDasharray="4 4"
             />
          )}
        </svg>
      </div>
      <div className="mt-4 flex items-center justify-center gap-6 text-xs">
        <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#0ea5e9] opacity-70"></span><span className="text-slate-300">Normal Range (&le;200)</span></div>
        <div className="flex items-center gap-1.5"><span className="w-3.5 h-3.5 rounded-full bg-[#f43f5e] opacity-90"></span><span className="text-slate-300 font-semibold">Severe Range (&gt;200)</span></div>
        <div className="flex items-center gap-1.5"><span className="w-4 border-t border-dashed border-slate-300"></span><span className="text-slate-300 font-semibold">Perfect Prediction (y=x)</span></div>
      </div>
    </div>
  );
}
"""

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = lines[:158] 
new_lines.append(hook_code + "\\n")
new_lines.append(multi_line_code + "\\n")
new_lines.append(model_scatter_code + "\\n")
new_lines.extend(lines[431:])

with open('src/App.jsx', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("SVG Zoom/Pan updates injected successfully!")
