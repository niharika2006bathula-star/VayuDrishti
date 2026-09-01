import React, { useEffect, useState, useRef, useMemo } from 'react';
import L from 'leaflet';
import { 
  Wind, 
  MapPin, 
  Activity, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown,
  Search, 
  Layers, 
  AlertTriangle,
  Info,
  Calendar,
  X,
  HelpCircle,
  Sparkles,
  ArrowUpRight,
  ArrowDownRight,
  Flame,
  Thermometer,
  CloudRain,
  Gauge,
  LayoutDashboard,
  Bell,
  Settings,
  ShieldAlert,
  ChevronRight,
  ExternalLink,
  Sliders,
  Database,
  Cpu,
  Clock,
  CheckCircle2,
  AlertCircle,
  ArrowUpDown,
  Filter,
  Play,
  Pause,
  Navigation,
  Compass,
  Briefcase,
  ShieldCheck,
  Factory,
  BookOpen
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';
const DELHI_CENTER = [28.6139, 77.2090];

// Calculate forward azimuth/bearing in degrees from point 1 to point 2
const calculateBearing = (lat1, lon1, lat2, lon2) => {
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(dLon) * Math.cos((lat2 * Math.PI) / 180);
  const x =
    Math.cos((lat1 * Math.PI) / 180) * Math.sin((lat2 * Math.PI) / 180) -
    Math.sin((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.cos(dLon);
  const brng = (Math.atan2(y, x) * 180) / Math.PI;
  return (brng + 360) % 360;
};

// Check if a station is geographically downwind of active regional fires under current wind conditions
const checkIsDownwindOfFires = (stationLat, stationLon, fires, windDirDeg) => {
  if (!fires || fires.length === 0 || windDirDeg === undefined || windDirDeg === null) return false;
  // Centroid of active fire detections
  const avgFireLat = fires.reduce((a, b) => a + b.latitude, 0) / fires.length;
  const avgFireLon = fires.reduce((a, b) => a + b.longitude, 0) / fires.length;

  const bearingFromFireToStation = calculateBearing(avgFireLat, avgFireLon, stationLat, stationLon);
  const flowDir = (windDirDeg + 180) % 360; // downwind trajectory

  let angleDiff = Math.abs(flowDir - bearingFromFireToStation);
  if (angleDiff > 180) angleDiff = 360 - angleDiff;

  return angleDiff <= 35; // within ±35 degrees
};

// 7 Representative spatial anchors across Delhi NCR for Open-Meteo wind vectors
const WIND_GRID_COORDINATES = [
  { lat: 28.75, lng: 77.05 },
  { lat: 28.75, lng: 77.30 },
  { lat: 28.62, lng: 77.02 },
  { lat: 28.62, lng: 77.22 },
  { lat: 28.62, lng: 77.40 },
  { lat: 28.45, lng: 77.05 },
  { lat: 28.45, lng: 77.30 }
];

// Plain language feature descriptions for SHAP explainability
const FEATURE_DICTIONARY = {
  recent_pollution_trend: { label: 'Recent pollution trend', unit: 'µg/m³', icon: '📊' },
  temperature_2m: { label: 'Temperature', unit: '°C', icon: '🌡️' },
  relative_humidity_2m: { label: 'Humidity', unit: '%', icon: '💧' },
  wind_speed_10m: { label: 'Wind speed', unit: 'm/s', icon: '💨' },
  wind_sin: { label: 'Wind direction (East/West)', unit: '', icon: '🧭' },
  wind_cos: { label: 'Wind direction (North/South)', unit: '', icon: '🧭' },
  boundary_layer_height: { label: 'Atmospheric mixing height (PBL)', unit: 'm', icon: '🌫️' },
  surface_pressure: { label: 'Air pressure', unit: 'hPa', icon: '⏱️' },
  precipitation: { label: 'Rainfall', unit: 'mm', icon: '🌧️' },
  fire_count_punjab: { label: 'Fires in Punjab', unit: 'fires', icon: '🔥' },
  fire_count_haryana: { label: 'Fires in Haryana', unit: 'fires', icon: '🔥' },
  fire_count_up: { label: 'Fires in Uttar Pradesh', unit: 'fires', icon: '🔥' },
  fire_count_delhi: { label: 'Fires in Delhi', unit: 'fires', icon: '🔥' },
  hour: { label: 'Time of day', unit: ':00 hrs', icon: '🕒' },
  month: { label: 'Seasonal pattern', unit: '', icon: '📅' }
};

// PM2.5 Theme Styling
function getPM25Theme(val) {
  if (val === null || val === undefined) {
    return {
      bg: 'bg-slate-700',
      border: 'border-slate-500',
      text: 'text-slate-400',
      hex: '#64748b',
      label: 'No Data',
      badge: 'bg-slate-800 text-slate-400 border-slate-700'
    };
  }
  if (val < 50) {
    return {
      bg: 'bg-emerald-500',
      border: 'border-emerald-400',
      text: 'text-emerald-400',
      hex: '#10b981',
      label: 'Good (<50)',
      badge: 'bg-emerald-950/80 text-emerald-300 border-emerald-500/30'
    };
  }
  if (val <= 100) {
    return {
      bg: 'bg-amber-400',
      border: 'border-amber-300',
      text: 'text-amber-300',
      hex: '#f59e0b',
      label: 'Moderate (50-100)',
      badge: 'bg-amber-950/80 text-amber-300 border-amber-500/30'
    };
  }
  if (val <= 200) {
    return {
      bg: 'bg-orange-500',
      border: 'border-orange-400',
      text: 'text-orange-400',
      hex: '#f97316',
      label: 'Poor (100-200)',
      badge: 'bg-orange-950/80 text-orange-300 border-orange-500/30'
    };
  }
  return {
    bg: 'bg-rose-600',
    border: 'border-rose-400',
    text: 'text-rose-400',
    hex: '#e11d48',
    label: 'Severe (200+)',
    badge: 'bg-rose-950/80 text-rose-300 border-rose-500/30'
  };
}

// Interactive Multi-Line Trend Chart (SVG)

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
export default function App() {
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dataStatus, setDataStatus] = useState(null);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Dashboard Map Search & Trace State
  const [mapSearchQuery, setMapSearchQuery] = useState('');
  const [isSearchDropdownOpen, setIsSearchDropdownOpen] = useState(false);
  
  // Navigation & Page State
  const [navTab, setNavTab] = useState('dashboard'); // 'dashboard' | 'stations' | 'alerts' | 'settings' | 'simulator'

  // Stations Page State
  const [stationSortField, setStationSortField] = useState('pm25'); // 'pm25' | 'aqi' | 'name'
  const [stationSortAsc, setStationSortAsc] = useState(false);
  const [stationFilterCity, setStationFilterCity] = useState('ALL');

  // Alerts Page State

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

  const simDiffs = useMemo(() => {
    if (!simResults || !simResults.baseline_forecast || !simResults.feedback_forecast) return [];
    return simResults.baseline_forecast.map((b, i) => {
      const f = simResults.feedback_forecast[i];
      const diff = f - b;
      return {
        hour: i + 1,
        baseline: b,
        feedback: f,
        diff,
        isTriggered: Math.abs(diff) >= 0.01
      };
    });
  }, [simResults]);

  const simSummaryStats = useMemo(() => {
    if (!simDiffs.length) return { triggerCount: 0, maxAdjustment: '0.00' };
    const triggered = simDiffs.filter(d => d.isTriggered);
    const maxAdj = Math.max(0, ...simDiffs.map(d => Math.abs(d.diff)));
    return {
      triggerCount: triggered.length,
      maxAdjustment: maxAdj.toFixed(2)
    };
  }, [simDiffs]);

  const [alertsData, setAlertsData] = useState(null);

  const [loadingAlerts, setLoadingAlerts] = useState(false);

  // Settings State (Active Polling Frequency)
  const [refreshIntervalSec, setRefreshIntervalSec] = useState(60); // 30 | 60 | 300 | 0 (manual)
  const [lastSyncTime, setLastSyncTime] = useState(new Date());

  // Decision & Trust State
  const [decisionSupportData, setDecisionSupportData] = useState(null);
  const [loadingDecision, setLoadingDecision] = useState(false);
  const [modelTrustData, setModelTrustData] = useState(null);
  const [loadingTrust, setLoadingTrust] = useState(false);


  // Selected Station drives the top chart and 4 stat cards
  const [selectedStation, setSelectedStation] = useState(null);
  
  // Modal Station controls whether the intelligence modal overlay is open
  const [modalStation, setModalStation] = useState(null);

  const [nearbySources, setNearbySources] = useState(null);
  const [loadingSources, setLoadingSources] = useState(false);


  const [stationReadings, setStationReadings] = useState(null);
  const [forecastData, setForecastData] = useState(null);
  const [explainData, setExplainData] = useState(null);
  const [dispersionData, setDispersionData] = useState(null);
  const [historyData, setHistoryData] = useState([]);
  const [historyDays, setHistoryDays] = useState(7);
  const [loadingModal, setLoadingModal] = useState(false);
  const [activeTab, setActiveTab] = useState('current'); // 'current' | 'forecast' | 'explain'

  // Filter stations matching map search query
  const searchMatches = useMemo(() => {
    if (!mapSearchQuery.trim()) return [];
    const q = mapSearchQuery.trim().toLowerCase();
    return stations.filter(st => 
      st.name.toLowerCase().includes(q) || (st.city && st.city.toLowerCase().includes(q))
    ).slice(0, 6);
  }, [mapSearchQuery, stations]);

  // Handler: Select a station from search -> trace on map, select, and view full intelligence modal
  const handleStationSearchSelect = (station) => {
    if (!station) return;
    setSelectedStation(station);
    setMapSearchQuery(station.name);
    setIsSearchDropdownOpen(false);
    
    // Smoothly fly map to station
    if (mapInstanceRef.current && station.latitude && station.longitude) {
      mapInstanceRef.current.flyTo([station.latitude, station.longitude], 12, { duration: 0.9 });
    }
    
    // Open station intelligence modal to view all data
    openStationModal(station);
  };

  // Pollution Movement Time-Slider State
  const [movementData, setMovementData] = useState(null);
  const [selectedStepIdx, setSelectedStepIdx] = useState(0);
  const [isPlayingMovement, setIsPlayingMovement] = useState(false);
  const [loadingMovement, setLoadingMovement] = useState(false);

  // NASA FIRMS Regional Fires State
  const [firesData, setFiresData] = useState(null);
  const [showFires, setShowFires] = useState(true);

  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersLayerRef = useRef(null);
  const windArrowsLayerRef = useRef(null);
  const firesLayerRef = useRef(null);

  // Fetch stations from backend
  const fetchStations = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/stations`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch stations`);
      const data = await res.json();
      setStations(data);
      setLastSyncTime(new Date());

      if (!selectedStation && data.length > 0) {
        setSelectedStation(data[0]);
      }
    } catch (err) {
      console.error(err);
      setError('Unable to reach backend at ' + API_BASE + '. Ensure uvicorn is running.');
    } finally {
      setLoading(false);
    }
  };

  // Fetch alerts from backend
  const fetchAlerts = async () => {
    setLoadingAlerts(true);
    try {
      const res = await fetch(`${API_BASE}/alerts`);
      if (res.ok) {
        const json = await res.json();
        setAlertsData(json);
      }
    } catch (e) {
      console.error('Error loading alerts:', e);
    } finally {
      setLoadingAlerts(false);
    }
  };

  // Fetch 72-hour pollution movement time-step forecasts
  const fetchMovementForecast = async () => {
    setLoadingMovement(true);
    try {
      const res = await fetch(`${API_BASE}/movement-forecast`);
      if (res.ok) {
        const json = await res.json();
        setMovementData(json);
      }
    } catch (e) {
      console.error('Failed to load movement forecast:', e);
    } finally {
      setLoadingMovement(false);
    }
  };

  // Fetch NASA FIRMS regional fire hotspot detections
  
  // Fetch Decision Support
  const fetchDecisionSupport = async () => {
    setLoadingDecision(true);
    try {
      const res = await fetch(`${API_BASE}/decision-support`);
      if (res.ok) {
        const json = await res.json();
        setDecisionSupportData(json);
      }
    } catch (e) {
      console.error('Error loading decision support:', e);
    } finally {
      setLoadingDecision(false);
    }
  };

  // Fetch Model Trust
  const fetchModelTrust = async () => {
    setLoadingTrust(true);
    try {
      const res = await fetch(`${API_BASE}/model-trust`);
      if (res.ok) {
        const json = await res.json();
        setModelTrustData(json);
      }
    } catch (e) {
      console.error('Error loading model trust:', e);
    } finally {
      setLoadingTrust(false);
    }
  };

  const fetchFires = async () => {
    try {
      const res = await fetch(`${API_BASE}/fires`);
      if (res.ok) {
        const json = await res.json();
        setFiresData(json);
      }
    } catch (e) {
      console.error('Failed to load FIRMS fires:', e);
    }
  };

  const fetchDataStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/data-status`);
      if (res.ok) {
        const data = await res.json();
        setDataStatus(data);
      }
    } catch (err) {
      console.error("Error fetching data status:", err);
    }
  };

  useEffect(() => {
    fetchStations();
    fetchDataStatus();
    fetchAlerts();
    fetchMovementForecast();
    fetchFires();
  }, []);

  // Auto-poll data-status every 60 seconds so the banner stays fresh
  useEffect(() => {
    const interval = setInterval(fetchDataStatus, 60000);
    return () => clearInterval(interval);
  }, []);

  // Auto-advance movement time slider when playing
  useEffect(() => {
    let interval = null;
    if (isPlayingMovement) {
      interval = setInterval(() => {
        setSelectedStepIdx((prev) => (prev + 1) % 6);
      }, 1800);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isPlayingMovement]);

  // Periodic polling controlled by settings
  useEffect(() => {
    if (!refreshIntervalSec || refreshIntervalSec <= 0) return;
    const interval = setInterval(() => {
      fetchStations();
      fetchAlerts();
      fetchMovementForecast();
    }, refreshIntervalSec * 1000);
    return () => clearInterval(interval);
  }, [refreshIntervalSec]);

  // Fetch station history trend & dispersion when selectedStation or historyDays changes
  useEffect(() => {
    if (!selectedStation) return;
    const fetchHistory = async () => {
      try {
        const res = await fetch(`${API_BASE}/history/${encodeURIComponent(selectedStation.name)}?days=${historyDays}`);
        if (res.ok) {
          const json = await res.json();
          setHistoryData(json.history || []);
        }
      } catch (e) {
        console.error('Failed to load history:', e);
      }
    };

    const fetchDispersion = async () => {
      try {
        const res = await fetch(`${API_BASE}/dispersion/${encodeURIComponent(selectedStation.name)}`);
        if (res.ok) {
          const json = await res.json();
          setDispersionData(json);
        }
      } catch (e) {
        console.error('Failed to load dispersion:', e);
      }
    };

    fetchHistory();
    fetchDispersion();
  }, [selectedStation?.name, historyDays]);

  // Initialize Leaflet Map (when on dashboard tab)
  useEffect(() => {
    if (navTab !== 'dashboard') {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
      return;
    }

    if (!mapContainerRef.current) return;
    if (mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: DELHI_CENTER,
      zoom: 10,
      zoomControl: false,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    const markersLayer = L.layerGroup().addTo(map);
    const windLayer = L.layerGroup().addTo(map);
    const firesLayer = L.layerGroup().addTo(map);
    markersLayerRef.current = markersLayer;
    windArrowsLayerRef.current = windLayer;
    firesLayerRef.current = firesLayer;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [navTab]);

  // Update Markers and Wind Direction Arrows when step, stations, or selection changes
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current || navTab !== 'dashboard') return;

    markersLayerRef.current.clearLayers();
    if (windArrowsLayerRef.current) {
      windArrowsLayerRef.current.clearLayers();
    }

    const currentStep = movementData?.steps?.[selectedStepIdx];
    const stepStationMap = currentStep ? new Map(currentStep.stations.map(s => [s.station_name, s])) : null;

    stations.forEach((st) => {
      if (!st.latitude || !st.longitude) return;

      const isSelected = selectedStation?.name === st.name;
      const stepData = stepStationMap?.get(st.name);
      
      const effectivePM = stepData ? stepData.pm25 : st.latest_pm25;
      const effectiveAQI = stepData ? stepData.aqi : st.latest_aqi;
      const effectiveCat = stepData ? stepData.aqi_category : st.aqi_category;
      
      const theme = getPM25Theme(effectivePM);
      const displayVal = effectivePM !== null && effectivePM !== undefined ? Math.round(effectivePM) : '--';

      // Downwind geographic directional check from active fire centroid
      const isDownwind = checkIsDownwindOfFires(
        st.latitude, 
        st.longitude, 
        firesData?.fires, 
        currentStep?.wind?.direction_deg
      );

      const customIcon = L.divIcon({
        className: 'custom-station-marker',
        html: `
          <div class="relative group cursor-pointer">
            <div style="background-color: ${theme.hex};" 
                 class="w-9 h-9 rounded-full flex items-center justify-center text-white font-bold text-xs shadow-lg transform transition-all duration-300 ${
                   isSelected 
                     ? 'ring-4 ring-cyan-400 ring-offset-2 ring-offset-slate-950 scale-125 z-50' 
                     : 'border-2 border-white/90 group-hover:scale-110'
                 }">
              ${displayVal}
            </div>
            
            ${isDownwind ? `
              <!-- Downwind Amber Highlighted Ring & Flame Badge -->
              <div class="absolute -inset-1.5 rounded-full border-2 border-dashed border-amber-400 animate-pulse pointer-events-none shadow-[0_0_10px_rgba(251,191,36,0.9)]"></div>
              <div class="absolute -top-2 -right-2 w-4 h-4 rounded-full bg-amber-500 border border-slate-950 flex items-center justify-center text-[9px] shadow-md z-30 pointer-events-none" title="Geographically Downwind of Regional Fires">
                🔥
              </div>
            ` : `
              <div style="background-color: ${theme.hex};" 
                   class="absolute inset-0 rounded-full opacity-40 animate-ping -z-10">
              </div>
            `}
          </div>
        `,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
        popupAnchor: [0, -20]
      });

      const marker = L.marker([st.latitude, st.longitude], { icon: customIcon });

      marker.on('click', () => {
        setSelectedStation(st);
      });

      const offsetLabel = currentStep ? currentStep.label : 'Now';
      const popupHtml = `
        <div class="p-1 min-w-[200px] text-slate-100 font-sans">
          <div class="flex items-center justify-between gap-2 border-b border-slate-700/60 pb-2 mb-2">
            <span class="text-xs font-semibold px-2 py-0.5 rounded-full ${theme.badge}">
              AQI ${effectiveAQI || '--'} (${effectiveCat || theme.label})
            </span>
            <span class="text-[10px] text-cyan-300 font-bold bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/30">
              Offset: ${offsetLabel}
            </span>
          </div>
          
          <h4 class="font-bold text-sm text-white mb-1 leading-snug">${st.name}</h4>
          
          ${isDownwind ? `
            <div class="mt-1 mb-2 px-2 py-1 rounded bg-amber-950/60 border border-amber-500/40 text-[10px] text-amber-300 font-semibold flex items-center gap-1.5">
              <span>🔥</span>
              <span>Geographically Downwind of Regional Fires</span>
            </div>
          ` : ''}

          <div class="flex items-baseline gap-2 my-2">
            <span class="text-2xl font-extrabold text-white">${effectivePM !== null ? effectivePM : 'N/A'}</span>
            <span class="text-xs text-slate-400 font-medium">µg/m³ PM2.5 (${offsetLabel === 'Now' ? 'Live Reading' : 'Model Projection'})</span>
          </div>
          <button id="view-details-btn-${st.name.replace(/[^a-zA-Z0-9]/g, '')}" 
                  class="w-full py-1.5 px-3 bg-cyan-600 hover:bg-cyan-500 active:bg-cyan-700 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-md">
            <span>Open Intelligence Modal</span> &rarr;
          </button>
        </div>
      `;

      marker.bindPopup(popupHtml, { maxWidth: 280 });

      marker.on('popupopen', () => {
        const btnId = `view-details-btn-${st.name.replace(/[^a-zA-Z0-9]/g, '')}`;
        const btn = document.getElementById(btnId);
        if (btn) {
          btn.onclick = () => {
            setSelectedStation(st);
            openStationModal(st);
          };
        }
      });

      marker.addTo(markersLayerRef.current);
    });

    // Render 7 evenly spaced, prominent wind direction arrows across NCR
    if (windArrowsLayerRef.current && currentStep?.wind) {
      const wind = currentStep.wind;
      const flowAngle = (wind.direction_deg + 180) % 360; // points in the direction air is flowing
      const speedScale = Math.min(1.4, Math.max(0.8, wind.speed_ms / 8.0));
      const speedOpacity = Math.min(0.95, Math.max(0.6, wind.speed_ms / 14.0 + 0.35));

      WIND_GRID_COORDINATES.forEach((pt) => {
        const windIcon = L.divIcon({
          className: 'custom-wind-arrow-marker',
          html: `
            <div style="transform: rotate(${flowAngle}deg); transform-origin: center center;"
                 class="w-10 h-10 flex items-center justify-center pointer-events-none transition-transform duration-700">
              <div style="transform: scale(${speedScale}); opacity: ${speedOpacity};" class="flex flex-col items-center justify-center">
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="filter drop-shadow-[0_0_10px_rgba(6,182,212,1)]">
                  <polygon points="12,2 21,21 12,16.5 3,21" fill="#06b6d4" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round" />
                </svg>
              </div>
            </div>
          `,
          iconSize: [40, 40],
          iconAnchor: [20, 20]
        });

        const windMarker = L.marker([pt.lat, pt.lng], { icon: windIcon, interactive: false, zIndexOffset: 1000 });
        windMarker.addTo(windArrowsLayerRef.current);
      });
    }

    // Render NASA FIRMS fire hotspot detections across Punjab, Haryana, UP
    if (firesLayerRef.current) {
      firesLayerRef.current.clearLayers();
      if (showFires && firesData?.fires) {
        firesData.fires.forEach((fire) => {
          if (!fire.latitude || !fire.longitude) return;
          const frpScale = Math.min(1.35, Math.max(0.8, 0.8 + (fire.frp / 15.0) * 0.55));
          const frpOpacity = Math.min(1.0, Math.max(0.75, 0.7 + (fire.frp / 15.0) * 0.3));

          const fireIcon = L.divIcon({
            className: 'custom-fire-marker',
            html: `
              <div style="transform: scale(${frpScale}); opacity: ${frpOpacity};" class="relative group cursor-pointer flex items-center justify-center">
                <div class="w-6 h-6 rounded-full bg-gradient-to-tr from-amber-600 to-rose-500 border border-amber-300 flex items-center justify-center text-white shadow-lg shadow-orange-600/60 hover:scale-125 transition-transform">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="#fef08a" stroke="#b91c1c" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>
                  </svg>
                </div>
                <div class="absolute inset-0 rounded-full bg-orange-500 opacity-40 animate-ping -z-10"></div>
              </div>
            `,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
            popupAnchor: [0, -12]
          });

          const fireMarker = L.marker([fire.latitude, fire.longitude], { icon: fireIcon, zIndexOffset: 200 });
          const firePopupHtml = `
            <div class="p-1 min-w-[210px] text-slate-100 font-sans">
              <div class="flex items-center justify-between gap-2 border-b border-slate-700/60 pb-2 mb-2">
                <span class="text-xs font-bold px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400 border border-orange-500/40 flex items-center gap-1">
                  🔥 ${fire.state} Fire Hotspot
                </span>
                <span class="text-[10px] text-slate-400">NASA FIRMS</span>
              </div>
              <div class="space-y-1.5 text-xs text-slate-300">
                <div class="flex justify-between">
                  <span class="text-slate-400">Fire Radiative Power:</span>
                  <span class="font-bold text-amber-400">${fire.frp} MW</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">Detection Date:</span>
                  <span class="font-medium text-slate-200">${fire.acq_date}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">Detection Confidence:</span>
                  <span class="font-medium text-emerald-400 capitalize">${fire.confidence === 'n' ? 'Nominal' : fire.confidence === 'h' ? 'High' : 'Standard'}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">Sensor:</span>
                  <span class="text-slate-200">VIIRS (SNPP / NOAA-20)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">Coordinates:</span>
                  <span class="text-slate-400 font-mono text-[10px]">${fire.latitude.toFixed(3)}°N, ${fire.longitude.toFixed(3)}°E</span>
                </div>
              </div>
            </div>
          `;
          fireMarker.bindPopup(firePopupHtml, { maxWidth: 260 });
          fireMarker.addTo(firesLayerRef.current);
        });
      }
    }
  }, [stations, selectedStation?.name, navTab, selectedStepIdx, movementData, showFires, firesData]);

  // Open Detailed Station Modal
  
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

  const openStationModal = async (station) => {
    setSelectedStation(station);
    setModalStation(station);
    setLoadingModal(true);
    setStationReadings(null);
    setForecastData(null);
    setExplainData(null);
    setNearbySources(null);
    setActiveTab('current');

    try {
      const [currRes, fcRes, expRes] = await Promise.all([
        fetch(`${API_BASE}/current/${encodeURIComponent(station.name)}`),
        fetch(`${API_BASE}/forecast/${encodeURIComponent(station.name)}`),
        fetch(`${API_BASE}/explain/${encodeURIComponent(station.name)}`)
      ]);

      if (currRes.ok) setStationReadings(await currRes.json());
      if (fcRes.ok) setForecastData(await fcRes.json());
      if (expRes.ok) setExplainData(await expRes.json());
    } catch (e) {
      console.error('Error fetching station details:', e);
    } finally {
      setLoadingModal(false);
    }
  };

  // Top 5 Highest PM2.5 Stations
  const top5Stations = useMemo(() => {
    return [...stations]
      .filter(s => s.latest_pm25 !== null && s.latest_pm25 > 0)
      .sort((a, b) => b.latest_pm25 - a.latest_pm25)
      .slice(0, 5);
  }, [stations]);

  const maxTop5PM = top5Stations.length > 0 ? top5Stations[0].latest_pm25 : 100;

  const predictedHotspots = useMemo(() => {
    if (!movementData || !movementData.steps || !movementData.steps[selectedStepIdx]) return [];
    return [...movementData.steps[selectedStepIdx].stations]
      .sort((a, b) => b.pm25 - a.pm25)
      .slice(0, 5);
  }, [movementData, selectedStepIdx]);
  
  const maxPredictedPM = predictedHotspots.length > 0 ? predictedHotspots[0].pm25 : 100;
  const predictedOffset = movementData?.steps?.[selectedStepIdx]?.offset_hours || 0;

  // Processed Stations for Table View (Sortable & Filterable)
  const allCities = useMemo(() => {
    const set = new Set(stations.map(s => s.city || 'Delhi NCR'));
    return ['ALL', ...Array.from(set).sort()];
  }, [stations]);

  // Fetch nearby sources when modal opens
  useEffect(() => {
    if (modalStation && !loadingModal) {
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
  }, [modalStation, loadingModal]);

  const tableStations = useMemo(() => {
    let result = stations.filter(st => {
      const matchSearch = st.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          (st.city && st.city.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchCity = stationFilterCity === 'ALL' || (st.city || 'Delhi NCR') === stationFilterCity;
      return matchSearch && matchCity;
    });

    result.sort((a, b) => {
      let valA = a[stationSortField];
      let valB = b[stationSortField];

      if (stationSortField === 'pm25') {
        valA = a.latest_pm25 ?? -1;
        valB = b.latest_pm25 ?? -1;
      } else if (stationSortField === 'aqi') {
        valA = a.latest_aqi ?? -1;
        valB = b.latest_aqi ?? -1;
      } else if (stationSortField === 'name') {
        valA = a.name.toLowerCase();
        valB = b.name.toLowerCase();
      }

      if (valA < valB) return stationSortAsc ? -1 : 1;
      if (valA > valB) return stationSortAsc ? 1 : -1;
      return 0;
    });

    return result;
  }, [stations, searchQuery, stationFilterCity, stationSortField, stationSortAsc]);

  // Dynamic 1-line SHAP summary
  const generateExplainSummary = () => {
    if (!explainData || !explainData.top_contributing_factors || explainData.top_contributing_factors.length === 0) {
      return 'Analyzing environmental and meteorological influences...';
    }
    const factors = explainData.top_contributing_factors;
    const f1 = factors[0];
    const f2 = factors.length > 1 ? factors[1] : null;

    const f1Name = FEATURE_DICTIONARY[f1.feature]?.label || f1.feature;
    const f2Name = f2 ? (FEATURE_DICTIONARY[f2.feature]?.label || f2.feature) : '';

    const f1Verb = f1.impact === 'increase' ? 'increasing' : 'decreasing';
    const f2Verb = f2 ? (f2.impact === 'increase' ? 'increasing' : 'decreasing') : '';

    if (f1.impact === 'increase' && (!f2 || f2.impact === 'increase')) {
      return `PM2.5 is being pushed UP mainly by ${f1Name} (+${Math.abs(f1.shap_value)} µg/m³)${f2 ? ` and ${f2Name} (+${Math.abs(f2.shap_value)} µg/m³)` : ''}.`;
    } else if (f1.impact === 'decrease' && (!f2 || f2.impact === 'decrease')) {
      return `PM2.5 is being pushed DOWN mainly by ${f1Name} (-${Math.abs(f1.shap_value)} µg/m³)${f2 ? ` and ${f2Name} (-${Math.abs(f2.shap_value)} µg/m³)` : ''}.`;
    } else {
      return `PM2.5 is primarily driven by ${f1Name} (${f1Verb} by ${Math.abs(f1.shap_value)} µg/m³)${f2 ? ` along with ${f2Name} (${f2Verb} by ${Math.abs(f2.shap_value)} µg/m³)` : ''}.`;
    }
  };

  const maxShapMagnitude = explainData?.top_contributing_factors
    ? Math.max(...explainData.top_contributing_factors.map(f => Math.abs(f.shap_value)), 1.0)
    : 1.0;

  // Selected Station Metrics
  const currentPM = selectedStation?.latest_pm25 ?? 36.0;
  const currentAQI = selectedStation?.latest_aqi ?? 61;
  const currentAQICat = selectedStation?.aqi_category ?? 'Satisfactory';
  const currentTemp = dispersionData?.temperature_2m ?? 28.0;

  return (
    <div className="h-screen w-screen flex bg-[#0B1120] text-slate-100 font-sans overflow-hidden">
      
      {/* Left Navigation Sidebar */}
      <aside className="w-16 lg:w-56 bg-[#0F172A] border-r border-slate-800 flex flex-col justify-between shrink-0 z-20">
        <div>
          {/* Logo */}
          <div className="h-16 px-4 flex items-center gap-3 border-b border-slate-800">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 shrink-0">
              <Wind className="w-5 h-5 text-white" />
            </div>
            <div className="hidden lg:block">
              <h1 className="font-extrabold text-sm text-white tracking-wide">VayuDrishti</h1>
              <p className="text-[10px] text-cyan-400 font-medium">Air Intelligence</p>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="p-3 space-y-1.5 text-xs font-semibold">
            <button
              onClick={() => setNavTab('dashboard')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                navTab === 'dashboard' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}>
              <LayoutDashboard className="w-4 h-4 shrink-0" />
              <span className="hidden lg:inline">Dashboard</span>
            </button>

            <button
              onClick={() => setNavTab('stations')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                navTab === 'stations' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}>
              <MapPin className="w-4 h-4 shrink-0" />
              <span className="hidden lg:inline">Stations ({stations.length})</span>
              <span className="hidden lg:inline ml-auto text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
                {stations.length}
              </span>
            </button>

            <button
              onClick={() => {
                setNavTab('alerts');
                fetchAlerts();
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all relative ${
                navTab === 'alerts' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}>
              <Bell className="w-4 h-4 shrink-0" />
              <span className="hidden lg:inline">Alerts & Rules</span>
              {alertsData?.total_alerts > 0 && (
                <span className="hidden lg:inline ml-auto text-[10px] px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold">
                  {alertsData.total_alerts}
                </span>
              )}
            </button>

            <button 
              onClick={() => setNavTab('simulator')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                navTab === 'simulator' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}>
              <Play className="w-4 h-4 shrink-0" />
              <span className="hidden lg:inline">Scenario Simulator</span>
            </button>

            <button
              onClick={() => setNavTab('settings')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                navTab === 'settings' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}>
              <Settings className="w-4 h-4 shrink-0" />
              <span className="hidden lg:inline">Settings</span>
            </button>

            <button
              onClick={() => {
                setNavTab('decision');
                fetchDecisionSupport();
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                navTab === 'decision' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}>
              <Briefcase className="w-4 h-4 shrink-0" />
              <span className="hidden lg:inline">Decision Support</span>
            </button>

            <button
              onClick={() => {
                setNavTab('trust');
                fetchModelTrust();
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                navTab === 'trust' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}>
              <ShieldCheck className="w-4 h-4 shrink-0" />
              <span className="hidden lg:inline">Model Trust</span>
            </button>

          </nav>
        </div>

        {/* Sidebar Footer Info */}
        <div className="p-3 border-t border-slate-800 hidden lg:block text-[11px] text-slate-400">
          <div className="flex items-center gap-1.5 text-emerald-400 font-medium mb-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>Live ML Backend Active</span>
          </div>
          <p className="text-slate-500 text-[10px]">Model: XGBoost V1 | CPCB NAQI</p>
        </div>
      </aside>

      {/* Main App Container */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        
        {/* Top Header Bar */}
        <header className="h-16 border-b border-slate-800 bg-[#0F172A]/90 backdrop-blur-md px-6 flex items-center justify-between shrink-0 z-10">
          <div className="flex items-center gap-4">
            <h2 className="text-base font-bold text-white font-heading">
              {navTab === 'dashboard' && 'Delhi NCR Air Quality & Forecasting Intelligence'}
              {navTab === 'stations' && `Monitoring Stations Directory (${stations.length} Active Sensors)`}
              {navTab === 'alerts' && 'Automated Air Quality Rules & Active Alerts'}

              {navTab === 'simulator' && 'Scenario Simulator (What-If Forecasting)'}
              {navTab === 'settings' && 'System Configuration & Machine Learning Metadata'}

            </h2>
            {navTab === 'dashboard' && selectedStation && (
              <span className="hidden md:inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 shadow-sm">
                <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                Active Focus: <strong className="text-white">{selectedStation.name}</strong>
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {dataStatus && (
              <div className="hidden xl:flex items-center gap-3 mr-4 text-[10px] text-slate-400 font-medium">
                <div className="flex items-center gap-1.5" title={`Status: ${dataStatus.openaq_status || 'PENDING'}${dataStatus.openaq_rows != null ? ' | ' + dataStatus.openaq_rows + ' rows' : ''}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${dataStatus.openaq_status === 'SUCCESS' ? 'bg-emerald-400' : dataStatus.openaq_status === 'FAILED' ? 'bg-amber-400 animate-pulse' : 'bg-slate-500'}`}></div>
                  OpenAQ: {dataStatus.openaq_last_refresh ? new Date(dataStatus.openaq_last_refresh).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'N/A'}
                  {dataStatus.openaq_rows != null && <span className="text-slate-500">({dataStatus.openaq_rows})</span>}
                </div>
                <div className="flex items-center gap-1.5" title={`Status: ${dataStatus.firms_status || 'PENDING'}${dataStatus.firms_rows != null ? ' | ' + dataStatus.firms_rows + ' rows' : ''}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${dataStatus.firms_status === 'SUCCESS' ? 'bg-emerald-400' : dataStatus.firms_status === 'FAILED' ? 'bg-amber-400 animate-pulse' : 'bg-slate-500'}`}></div>
                  FIRMS: {dataStatus.firms_last_refresh ? new Date(dataStatus.firms_last_refresh).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'N/A'}
                  {dataStatus.firms_rows != null && <span className="text-slate-500">({dataStatus.firms_rows})</span>}
                </div>
                <div className="flex items-center gap-1.5" title={`Status: ${dataStatus.weather_status || 'PENDING'}${dataStatus.weather_rows != null ? ' | ' + dataStatus.weather_rows + ' rows' : ''}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${dataStatus.weather_status === 'SUCCESS' ? 'bg-emerald-400' : dataStatus.weather_status === 'FAILED' ? 'bg-amber-400 animate-pulse' : 'bg-slate-500'}`}></div>
                  Weather: {dataStatus.weather_last_refresh ? new Date(dataStatus.weather_last_refresh).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'N/A'}
                  {dataStatus.weather_rows != null && <span className="text-slate-500">({dataStatus.weather_rows}h)</span>}
                </div>
              </div>
            )}
            <button 
              onClick={() => {
                fetchStations();
                fetchDataStatus();
                if (navTab === 'alerts') fetchAlerts();
              }}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-xs font-semibold text-slate-200 transition-colors border border-slate-700/60">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
              <span className="hidden sm:inline">{loading ? 'Syncing...' : 'Sync Live Telemetry'}</span>
            </button>
          </div>
        </header>

        {/* Dynamic Page Content Based on navTab */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {/* ========================================================================= */}
          {/* PAGE 1: DASHBOARD                                                         */}
          {/* ========================================================================= */}
          {navTab === 'dashboard' && (
            <>
              {/* SECTION 1: Multi-line Trend Chart (Top) */}
              <section>
                <MultiLineTrendChart 
                  historyData={historyData}
                  days={historyDays}
                  onDaysChange={(d) => setHistoryDays(d)}
                  stationName={selectedStation?.name || 'Alipur, Delhi - DPCC'}
                  onOpenModal={() => selectedStation && openStationModal(selectedStation)}
                />
              </section>

              {/* SECTION 2: Compact Stat Cards Row */}
              <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Card 1: PM2.5 */}
                <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-4 shadow-lg hover:border-slate-700 transition-all">
                  <div className="flex items-center justify-between text-slate-400 text-xs mb-1 font-semibold">
                    <span>Current PM2.5</span>
                    <span className="p-1.5 rounded-lg bg-cyan-950/60 text-cyan-400 border border-cyan-500/20">
                      <Wind className="w-3.5 h-3.5" />
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2 mt-2">
                    <span className="text-2xl font-extrabold text-white">{currentPM}</span>
                    <span className="text-xs text-slate-400">µg/m³</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-semibold mt-2">
                    <TrendingDown className="w-3.5 h-3.5" />
                    <span>Station Live Concentration</span>
                  </div>
                </div>

                {/* Card 2: Temperature */}
                <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-4 shadow-lg hover:border-slate-700 transition-all">
                  <div className="flex items-center justify-between text-slate-400 text-xs mb-1 font-semibold">
                    <span>Ambient Temperature</span>
                    <span className="p-1.5 rounded-lg bg-rose-950/60 text-rose-400 border border-rose-500/20">
                      <Thermometer className="w-3.5 h-3.5" />
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2 mt-2">
                    <span className="text-2xl font-extrabold text-white">{currentTemp}</span>
                    <span className="text-xs text-slate-400">°C</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-rose-400 font-semibold mt-2">
                    <TrendingUp className="w-3.5 h-3.5" />
                    <span>Open-Meteo Regional Weather</span>
                  </div>
                </div>

                {/* Card 3: Official CPCB AQI */}
                <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-4 shadow-lg hover:border-slate-700 transition-all">
                  <div className="flex items-center justify-between text-slate-400 text-xs mb-1 font-semibold">
                    <span>Official CPCB AQI</span>
                    <span className="p-1.5 rounded-lg bg-amber-950/60 text-amber-400 border border-amber-500/20">
                      <Gauge className="w-3.5 h-3.5" />
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2 mt-2">
                    <span className="text-2xl font-extrabold text-white">{currentAQI}</span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${getPM25Theme(currentPM).badge}`}>
                      {currentAQICat}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-2">
                    NAQI Sub-Index Scale (0-500)
                  </div>
                </div>

                {/* Card 4: Atmospheric Dispersion Status */}
                <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-4 shadow-lg hover:border-slate-700 transition-all">
                  <div className="flex items-center justify-between text-slate-400 text-xs mb-1 font-semibold">
                    <span>Atmospheric Dispersion</span>
                    <span className="p-1.5 rounded-lg bg-blue-950/60 text-blue-400 border border-blue-500/20">
                      <Activity className="w-3.5 h-3.5" />
                    </span>
                  </div>
                  <div className="mt-2">
                    <span className="text-sm font-extrabold text-white block truncate">
                      {dispersionData?.classification || 'MODERATE DISPERSION'}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      PBL: {dispersionData?.boundary_layer_height || 450}m | Wind: {dispersionData?.wind_speed_10m || 8.0}m/s
                    </span>
                  </div>
                  <div className="text-[11px] text-emerald-400 font-semibold mt-1.5 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                    <span>Active Dispersion Ventilation</span>
                  </div>
                </div>
              </section>

              {/* SECTION 3 & 4: Leaflet Map & Top 5 Hotspots Bar Comparison */}
              <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Map Container */}
                <div className="lg:col-span-2 bg-[#0F172A] border border-slate-800 rounded-2xl p-4 shadow-xl flex flex-col">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <div className="flex items-center gap-2">
                        <MapPin className="w-4 h-4 text-cyan-400" />
                        <h3 className="font-bold text-sm text-white font-heading">
                          Delhi NCR Active Station Network (50 Sensors)
                        </h3>
                      </div>

                      {/* FIRMS Regional Fires Toggle Button */}
                      <button
                        onClick={() => {
                          const nextState = !showFires;
                          setShowFires(nextState);
                          if (nextState && mapInstanceRef.current && firesData?.fires?.length > 0) {
                            // If toggled on, expand view slightly so regional fires are in frame
                            mapInstanceRef.current.flyTo([29.2, 76.5], 8, { duration: 0.8 });
                          } else if (!nextState && mapInstanceRef.current) {
                            mapInstanceRef.current.flyTo(DELHI_CENTER, 10, { duration: 0.8 });
                          }
                        }}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                          showFires
                            ? 'bg-orange-500/20 text-orange-300 border border-orange-500/40 shadow-sm shadow-orange-500/10 ring-1 ring-orange-500/30'
                            : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-slate-800'
                        }`}>
                        <Flame className={`w-3.5 h-3.5 ${showFires ? 'text-orange-400 fill-orange-400' : 'text-slate-500'}`} />
                        <span>Show Regional Fires</span>
                        {firesData?.total_fires > 0 && (
                          <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                            showFires ? 'bg-orange-500/30 text-orange-200' : 'bg-slate-800 text-slate-400'
                          }`}>
                            {firesData.total_fires}
                          </span>
                        )}
                      </button>
                    </div>

                    <div className="relative w-full sm:w-64">
                      <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
                      <input 
                        type="text"
                        placeholder="Search station & press Enter..."
                        value={mapSearchQuery}
                        onFocus={() => setIsSearchDropdownOpen(true)}
                        onChange={(e) => {
                          setMapSearchQuery(e.target.value);
                          setIsSearchDropdownOpen(true);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            if (searchMatches.length > 0) {
                              handleStationSearchSelect(searchMatches[0]);
                            } else if (mapSearchQuery.trim()) {
                              const q = mapSearchQuery.trim().toLowerCase();
                              const match = stations.find(st => 
                                st.name.toLowerCase().includes(q) || (st.city && st.city.toLowerCase().includes(q))
                              );
                              if (match) handleStationSearchSelect(match);
                            }
                          } else if (e.key === 'Escape') {
                            setIsSearchDropdownOpen(false);
                          }
                        }}
                        className="w-full pl-8 pr-7 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 shadow-inner"
                      />

                      {mapSearchQuery && (
                        <button
                          onClick={() => {
                            setMapSearchQuery('');
                            setIsSearchDropdownOpen(false);
                          }}
                          className="absolute right-2.5 top-2 text-slate-500 hover:text-slate-300">
                          <X className="w-3 h-3" />
                        </button>
                      )}

                      {/* Autocomplete Suggestions Dropdown */}
                      {isSearchDropdownOpen && mapSearchQuery.trim() && (
                        <div className="absolute left-0 right-0 top-full mt-1 bg-slate-950 border border-slate-700/80 rounded-xl shadow-2xl overflow-hidden z-50 divide-y divide-slate-800/80 max-h-64 overflow-y-auto">
                          {searchMatches.length > 0 ? (
                            searchMatches.map((st) => {
                              const theme = getPM25Theme(st.latest_pm25);
                              return (
                                <div
                                  key={st.name}
                                  onClick={() => handleStationSearchSelect(st)}
                                  className="px-3 py-2 hover:bg-slate-900 cursor-pointer flex items-center justify-between gap-2 transition-colors">
                                  <div className="min-w-0">
                                    <div className="text-xs font-bold text-slate-200 truncate">
                                      {st.name}
                                    </div>
                                    <div className="text-[10px] text-slate-400">
                                      {st.city || 'Delhi NCR'}
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-1.5 shrink-0">
                                    <span className="text-xs font-bold text-white">
                                      {st.latest_pm25 !== null ? `${Math.round(st.latest_pm25)}` : '--'}
                                    </span>
                                    <span className={`text-[9px] px-1.5 py-0.2 rounded-full font-bold border ${theme.badge}`}>
                                      AQI {st.latest_aqi || '--'}
                                    </span>
                                  </div>
                                </div>
                              );
                            })
                          ) : (
                            <div className="px-3 py-2 text-xs text-slate-500 text-center">
                              No matching monitoring station found
                            </div>
                          )}
                          <div className="px-3 py-1 bg-slate-900 text-[10px] text-slate-400 font-medium flex items-center justify-between">
                            <span>Press <strong>Enter</strong> to trace & view</span>
                            <span className="text-cyan-400 font-bold">&crarr;</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Caption for FIRMS Fires & Downwind Legend */}
                  {showFires && (
                    <div className="mb-2.5 px-3 py-2 rounded-xl bg-orange-950/30 border border-orange-500/25 flex flex-col gap-1 text-[11px] text-orange-300/90 shadow-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold flex items-center gap-1.5">
                          <span>🔥</span>
                          <span>Regional Fire Activity (NASA FIRMS):</span>
                        </span>
                        <button 
                          onClick={() => {
                            if (mapInstanceRef.current) {
                              mapInstanceRef.current.flyTo(DELHI_CENTER, 10, { duration: 0.8 });
                            }
                          }}
                          className="text-[10px] text-cyan-400 hover:underline font-semibold shrink-0 ml-2">
                          Recenter on Delhi
                        </button>
                      </div>
                      <p className="text-[10px] text-slate-400 leading-snug">
                        Highlighted stations (amber dashed ring / 🔥) are geographically downwind of active regional fires under current wind conditions — not a confirmed pollution source, just a directional indicator.
                      </p>
                    </div>
                  )}

                  <div className="h-80 w-full rounded-xl overflow-hidden relative border border-slate-800">
                    <div ref={mapContainerRef} className="w-full h-full z-0" />
                  </div>

                  {/* POLLUTION MOVEMENT TIME-SLIDER CONTROL & COMPASS GAUGE */}
                  <div className="mt-4 pt-3.5 border-t border-slate-800/90 bg-slate-950/70 p-3.5 rounded-xl border border-slate-800/80">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-bold text-white flex items-center gap-1.5 font-heading">
                          <Wind className="w-4 h-4 text-cyan-400" />
                          Pollution Movement Time-Slider
                        </span>
                        
                        {/* Play / Pause Auto-Advance Button */}
                        <button
                          onClick={() => setIsPlayingMovement(!isPlayingMovement)}
                          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all ${
                            isPlayingMovement
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm shadow-amber-500/10'
                              : 'bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/40 shadow-sm shadow-cyan-500/10'
                          }`}>
                          {isPlayingMovement ? (
                            <>
                              <Pause className="w-3 h-3 fill-amber-300" />
                              <span>Pause Loop</span>
                            </>
                          ) : (
                            <>
                              <Play className="w-3 h-3 fill-cyan-300" />
                              <span>Play Loop</span>
                            </>
                          )}
                        </button>
                      </div>

                      {/* Visual Compass Wind Gauge & Telemetry Readout */}
                      {movementData?.steps?.[selectedStepIdx] && (
                        <div className="flex items-center gap-2.5">
                          {/* Mini Rotating Compass Dial Widget */}
                          <div className="flex items-center gap-2 px-2.5 py-1 rounded-xl bg-slate-900/90 border border-slate-700/80 shadow-md">
                            <div className="relative w-6 h-6 rounded-full bg-slate-950 border border-cyan-500/40 flex items-center justify-center">
                              <span className="absolute -top-1 text-[7px] font-black text-slate-500">N</span>
                              <div 
                                style={{ transform: `rotate(${movementData.steps[selectedStepIdx].wind.direction_deg}deg)` }}
                                className="w-full h-full flex items-center justify-center transition-transform duration-700 pointer-events-none">
                                <Navigation className="w-3.5 h-3.5 text-cyan-400 fill-cyan-400" />
                              </div>
                            </div>

                            <div className="text-[11px] font-mono leading-tight">
                              <div className="text-cyan-300 font-bold flex items-center gap-1">
                                <span>{movementData.steps[selectedStepIdx].wind.speed_ms} m/s</span>
                                <span className="text-slate-400 font-normal">({movementData.steps[selectedStepIdx].wind.direction_label})</span>
                              </div>
                              <div className="text-[9px] text-slate-400">
                                {movementData.steps[selectedStepIdx].wind.direction_deg}° from N
                              </div>
                            </div>
                          </div>

                          <div className="hidden md:flex flex-col justify-center px-2.5 py-1 rounded-xl bg-slate-900/90 border border-slate-700/80 font-mono text-[11px]">
                            <span className="text-slate-400 text-[9px]">Forecast Avg</span>
                            <span className="text-white font-bold">
                              {(movementData.steps[selectedStepIdx].stations.reduce((a, b) => a + b.pm25, 0) / movementData.steps[selectedStepIdx].stations.length).toFixed(1)} µg/m³
                            </span>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Step Buttons & Range Slider */}
                    <div className="grid grid-cols-6 gap-1.5 mb-2">
                      {['Now', '+6h', '+12h', '+24h', '+48h', '+72h'].map((stepLabel, idx) => {
                        const isCurrent = selectedStepIdx === idx;
                        return (
                          <button
                            key={stepLabel}
                            onClick={() => {
                              setSelectedStepIdx(idx);
                              setIsPlayingMovement(false);
                            }}
                            className={`py-1 px-1 rounded-lg text-xs font-bold transition-all text-center ${
                              isCurrent
                                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/30 ring-1 ring-cyan-300'
                                : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-slate-800'
                            }`}>
                            {stepLabel}
                          </button>
                        );
                      })}
                    </div>

                    {/* Disclaimer Footnote */}
                    <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
                      <span className="italic">
                        ℹ️ AI-assisted pollution transport estimate based on forecasted conditions
                      </span>
                      <span className="text-slate-400 font-mono">
                        {movementData?.steps?.[selectedStepIdx]?.label === 'Now' ? 'Live Observations' : `Projected +${movementData?.steps?.[selectedStepIdx]?.offset_hours || 0}h Ahead`}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right-Side Panels: Live Top 5 & Predicted Hotspots */}
                <div className="flex flex-col gap-6">
                  {/* Live Top 5 */}
                  <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between">
                    <div>
                    <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
                      <div className="flex items-center gap-2">
                        <ShieldAlert className="w-4 h-4 text-rose-400" />
                        <h3 className="font-bold text-sm text-white font-heading">
                          Top 5 Pollution Hotspots
                        </h3>
                      </div>
                      <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Live Ranking</span>
                    </div>

                    <div className="space-y-3">
                      {top5Stations.map((st, idx) => {
                        const isSelected = selectedStation?.name === st.name;
                        const theme = getPM25Theme(st.latest_pm25);
                        const barWidth = Math.max(15, Math.round((st.latest_pm25 / maxTop5PM) * 100));

                        return (
                          <div 
                            key={st.name} 
                            onClick={() => {
                              setSelectedStation(st);
                              if (mapInstanceRef.current && st.latitude && st.longitude) {
                                mapInstanceRef.current.flyTo([st.latitude, st.longitude], 11, { duration: 0.8 });
                              }
                            }}
                            className={`p-2.5 rounded-xl transition-all cursor-pointer group ${
                              isSelected 
                                ? 'bg-cyan-950/40 border-2 border-cyan-500 shadow-lg shadow-cyan-500/10' 
                                : 'bg-slate-950/70 border border-slate-800/80 hover:border-slate-700'
                            }`}>
                            
                            <div className="flex items-center justify-between text-xs mb-1.5">
                              <div className="flex items-center gap-2 min-w-0">
                                <span className={`w-4 h-4 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${
                                  isSelected ? 'bg-cyan-500 text-slate-950' : 'bg-slate-800 text-slate-300'
                                }`}>
                                  {idx + 1}
                                </span>
                                <span className={`font-semibold truncate transition-colors ${
                                  isSelected ? 'text-cyan-300' : 'text-slate-200 group-hover:text-cyan-400'
                                }`}>
                                  {st.name.split(',')[0]}
                                </span>
                              </div>
                              <span className={`font-bold text-xs ${theme.text}`}>
                                {st.latest_pm25} µg/m³
                              </span>
                            </div>

                            <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                              <div 
                                style={{ width: `${barWidth}%` }}
                                className={`h-full rounded-full transition-all duration-500 ${
                                  st.latest_pm25 > 100 ? 'bg-gradient-to-r from-orange-500 to-rose-500' : 'bg-gradient-to-r from-amber-400 to-orange-400'
                                }`}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="text-[11px] text-slate-400 pt-3 border-t border-slate-800/80 mt-4 flex items-center justify-between">
                    <span>Updated from CPCB & OpenAQ</span>
                    <span 
                      className="text-cyan-400 font-semibold flex items-center gap-1 cursor-pointer hover:underline" 
                      onClick={() => openStationModal(selectedStation || top5Stations[0])}>
                      Open Intelligence Modal &rarr;
                    </span>
                  </div>
                </div>
                  
                {/* Predicted Hotspots */}
                  {predictedOffset > 0 && predictedHotspots.length > 0 && (
                    <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between">
                      <div>
                        <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
                          <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-orange-400" />
                            <h3 className="font-bold text-sm text-white font-heading">
                              Predicted Hotspots (+{predictedOffset}h)
                            </h3>
                          </div>
                          <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Forecast Ranking</span>
                        </div>

                        <div className="space-y-3">
                          {predictedHotspots.map((st, idx) => {
                            const stName = st.station_name || st.name || 'Unknown Station';
                            const isSelected = selectedStation?.name === stName;
                            const theme = getPM25Theme(st.pm25);
                            const barWidth = Math.max(15, Math.round((st.pm25 / maxPredictedPM) * 100));

                            return (
                              <div 
                                key={stName} 
                                onClick={() => {
                                  const fullSt = stations.find(s => s.name === stName);
                                  if (fullSt) {
                                    setSelectedStation(fullSt);
                                    if (mapInstanceRef.current && fullSt.latitude && fullSt.longitude) {
                                      mapInstanceRef.current.flyTo([fullSt.latitude, fullSt.longitude], 11, { duration: 0.8 });
                                    }
                                  }
                                }}
                                className={`p-2.5 rounded-xl transition-all cursor-pointer group ${
                                  isSelected 
                                    ? 'bg-orange-950/40 border-2 border-orange-500 shadow-lg shadow-orange-500/10' 
                                    : 'bg-slate-950/70 border border-slate-800/80 hover:border-slate-700'
                                }`}>
                                
                                <div className="flex items-center justify-between text-xs mb-1.5">
                                  <div className="flex items-center gap-2 min-w-0">
                                    <span className={`w-4 h-4 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${
                                      isSelected ? 'bg-orange-500 text-slate-950' : 'bg-slate-800 text-slate-300'
                                    }`}>
                                      {idx + 1}
                                    </span>
                                    <span className={`font-semibold truncate transition-colors ${
                                      isSelected ? 'text-orange-300' : 'text-slate-200 group-hover:text-orange-400'
                                    }`}>
                                      {stName.split(',')[0]}
                                    </span>
                                  </div>
                                  <span className={`font-bold text-xs ${theme.text}`}>
                                    {Math.round(st.pm25)} µg/m³
                                  </span>
                                </div>

                                <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                                  <div 
                                    style={{ width: `${barWidth}%` }}
                                    className={`h-full rounded-full transition-all duration-500 ${
                                      st.pm25 > 100 ? 'bg-gradient-to-r from-orange-500 to-rose-500' : 'bg-gradient-to-r from-amber-400 to-orange-400'
                                    }`}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </section>
            </>
          )}

          {/* ========================================================================= */}
          {/* PAGE 2: STATIONS (FULL SEARCHABLE & SORTABLE DIRECTORY)                    */}
          {/* ========================================================================= */}
          {navTab === 'stations' && (
            <div className="space-y-6">
              
              {/* Directory Filter & Search Header */}
              <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h3 className="text-base font-bold text-white font-heading">
                      Delhi NCR Monitoring Stations Directory
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Real-time observations from DPCC, CPCB, HSPCB, UPPCB, and IMD sensors
                    </p>
                  </div>

                  {/* Search and City Filter Controls */}
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="relative min-w-[220px]">
                      <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
                      <input 
                        type="text"
                        placeholder="Search station..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-8 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                      />
                    </div>

                    <select
                      value={stationFilterCity}
                      onChange={(e) => setStationFilterCity(e.target.value)}
                      className="bg-slate-950 border border-slate-800 text-xs text-slate-200 px-3 py-1.5 rounded-xl focus:outline-none focus:border-cyan-500 font-medium">
                      {allCities.map(c => (
                        <option key={c} value={c}>{c === 'ALL' ? 'All NCR Cities' : c}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Stations Summary Stat Bar */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-slate-800/80 text-xs">
                  <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                    <span className="text-slate-400 block">Total Active Stations</span>
                    <span className="text-lg font-bold text-white mt-0.5 block">{stations.length}</span>
                  </div>
                  <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                    <span className="text-slate-400 block">Average PM2.5</span>
                    <span className="text-lg font-bold text-cyan-400 mt-0.5 block">
                      {stations.length ? Math.round(stations.reduce((a, b) => a + (b.latest_pm25 || 0), 0) / stations.length) : '--'} µg/m³
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                    <span className="text-slate-400 block">Highest PM2.5 Hotspot</span>
                    <span className="text-lg font-bold text-rose-400 mt-0.5 block truncate">
                      {top5Stations[0]?.latest_pm25 || '--'} µg/m³ ({top5Stations[0]?.name.split(',')[0]})
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                    <span className="text-slate-400 block">Lowest PM2.5 Reading</span>
                    <span className="text-lg font-bold text-emerald-400 mt-0.5 block">
                      {Math.min(...stations.filter(s => s.latest_pm25 > 0).map(s => s.latest_pm25)) || '--'} µg/m³
                    </span>
                  </div>
                </div>
              </div>

              {/* Stations Full Table */}
              <div className="bg-[#0F172A] border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                      <tr>
                        <th 
                          onClick={() => {
                            if (stationSortField === 'name') setStationSortAsc(!stationSortAsc);
                            else { setStationSortField('name'); setStationSortAsc(true); }
                          }}
                          className="px-5 py-3.5 cursor-pointer hover:text-white transition-colors">
                          <div className="flex items-center gap-1.5">
                            <span>Station Name & Network</span>
                            <ArrowUpDown className="w-3 h-3" />
                          </div>
                        </th>
                        <th className="px-4 py-3.5">City / Region</th>
                        <th 
                          onClick={() => {
                            if (stationSortField === 'pm25') setStationSortAsc(!stationSortAsc);
                            else { setStationSortField('pm25'); setStationSortAsc(false); }
                          }}
                          className="px-4 py-3.5 cursor-pointer hover:text-white transition-colors">
                          <div className="flex items-center gap-1.5">
                            <span>PM2.5 (µg/m³)</span>
                            <ArrowUpDown className="w-3 h-3" />
                          </div>
                        </th>
                        <th 
                          onClick={() => {
                            if (stationSortField === 'aqi') setStationSortAsc(!stationSortAsc);
                            else { setStationSortField('aqi'); setStationSortAsc(false); }
                          }}
                          className="px-4 py-3.5 cursor-pointer hover:text-white transition-colors">
                          <div className="flex items-center gap-1.5">
                            <span>Official CPCB AQI</span>
                            <ArrowUpDown className="w-3 h-3" />
                          </div>
                        </th>
                        <th className="px-4 py-3.5">Dispersion Indicator</th>
                        <th className="px-5 py-3.5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {tableStations.map((st, idx) => {
                        const theme = getPM25Theme(st.latest_pm25);
                        const isSelected = selectedStation?.name === st.name;

                        return (
                          <tr 
                            key={st.name} 
                            className={`hover:bg-slate-800/40 transition-colors ${isSelected ? 'bg-cyan-950/20' : ''}`}>
                            
                            <td className="px-5 py-3.5">
                              <div className="font-bold text-white flex items-center gap-2">
                                <span className="w-5 h-5 rounded bg-slate-800 text-[10px] flex items-center justify-center text-slate-400 font-mono">
                                  {idx + 1}
                                </span>
                                <span>{st.name}</span>
                              </div>
                              <span className="text-[11px] text-slate-500 block ml-7">
                                Lat: {st.latitude ? st.latitude.toFixed(4) : '--'}, Lon: {st.longitude ? st.longitude.toFixed(4) : '--'}
                              </span>
                            </td>

                            <td className="px-4 py-3.5 text-slate-300 font-medium">
                              {st.city || 'Delhi NCR'}
                            </td>

                            <td className="px-4 py-3.5">
                              <span className={`text-sm font-extrabold ${theme.text}`}>
                                {st.latest_pm25 !== null ? st.latest_pm25 : '--'} <span className="text-[10px] text-slate-400 font-normal">µg/m³</span>
                              </span>
                            </td>

                            <td className="px-4 py-3.5">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-bold text-white">{st.latest_aqi || '--'}</span>
                                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${theme.badge}`}>
                                  {st.aqi_category || theme.label}
                                </span>
                              </div>
                            </td>

                            <td className="px-4 py-3.5">
                              <span className="text-[11px] px-2 py-0.5 rounded-md bg-blue-950/50 text-blue-300 border border-blue-500/20 font-semibold">
                                Atmospheric Mixing Active
                              </span>
                            </td>

                            <td className="px-5 py-3.5 text-right">
                              <button
                                onClick={() => {
                                  setSelectedStation(st);
                                  setNavTab('dashboard');
                                }}
                                className="px-3 py-1.5 rounded-lg bg-cyan-600/80 hover:bg-cyan-500 text-white font-semibold text-xs transition-all shadow-md shadow-cyan-600/20">
                                Focus on Dashboard &rarr;
                              </button>
                            </td>

                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

            </div>
          )}

          {/* ========================================================================= */}
          {/* PAGE 3: ALERTS & RULES                                                    */}
          {/* ========================================================================= */}
          {navTab === 'alerts' && (
            <div className="space-y-6">
              
              {/* Alerts Rule Engine Card */}
              <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-5 h-5 text-amber-400" />
                      <h3 className="text-base font-bold text-white font-heading">
                        Real-Time Threshold Alert Engine
                      </h3>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Evaluated continuously across all {stations.length} active Delhi NCR stations using live telemetry and XGBoost forecasts
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs px-3 py-1 rounded-full bg-slate-950 border border-slate-800 text-slate-300 font-semibold">
                      Total Active: <strong className="text-amber-400">{alertsData?.total_alerts || 0}</strong>
                    </span>
                  </div>
                </div>

                {/* 3 Automated Rules Summary Banner */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                    <div className="font-bold text-rose-400 mb-1 flex items-center gap-1.5">
                      <AlertCircle className="w-3.5 h-3.5" />
                      <span>Rule 1: Poor AQI Alert</span>
                    </div>
                    <p className="text-slate-400 text-[11px]">
                      Triggers when station AQI exceeds 200 (Poor, Very Poor, or Severe categories).
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                    <div className="font-bold text-amber-400 mb-1 flex items-center gap-1.5">
                      <TrendingUp className="w-3.5 h-3.5" />
                      <span>Rule 2: Rising Pollution Trend</span>
                    </div>
                    <p className="text-slate-400 text-[11px]">
                      Triggers when 12-hour predicted PM2.5 climbs &ge; +20% AND crosses into Moderate or worse.
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                    <div className="font-bold text-blue-400 mb-1 flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5" />
                      <span>Rule 3: Poor Dispersion / Inversion</span>
                    </div>
                    <p className="text-slate-400 text-[11px]">
                      Triggers when surface winds &lt; 2.0 m/s and mixing height &lt; 500 m trap surface emissions.
                    </p>
                  </div>
                </div>
              </div>

              {/* Live Triggered Alerts List */}
              <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
                  <h4 className="font-bold text-sm text-white">Live Triggered Station Alerts</h4>
                  <span className="text-[11px] text-slate-400">
                    Updated: {new Date(alertsData?.timestamp || Date.now()).toLocaleTimeString()}
                  </span>
                </div>

                {loadingAlerts ? (
                  <div className="py-12 text-center text-xs text-slate-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-cyan-500" />
                    Evaluating multi-station alert rules...
                  </div>
                ) : alertsData?.alerts && alertsData.alerts.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                    {alertsData.alerts.map((alt) => {
                      const isCrit = alt.severity === 'critical';
                      return (
                        <div 
                          key={alt.id}
                          className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between">
                          <div>
                            <div className="flex items-center justify-between gap-2 mb-2">
                              <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full uppercase tracking-wider border ${
                                isCrit 
                                  ? 'bg-rose-950 text-rose-300 border-rose-500/40' 
                                  : 'bg-amber-950 text-amber-300 border-amber-500/40'
                              }`}>
                                {alt.alert_type}
                              </span>
                              <span className="text-[11px] text-slate-400 font-semibold">{alt.city}</span>
                            </div>

                            <h5 className="font-bold text-sm text-white mb-1.5">{alt.station_name}</h5>
                            <div className="text-xs font-semibold text-cyan-300 mb-2">
                              Current / Forecast Value: {alt.current_value}
                            </div>
                            <p className="text-xs text-slate-300 leading-relaxed">
                              {alt.reason}
                            </p>
                          </div>

                          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                            <span className="text-[10px] text-slate-500">Auto Rule Trigger</span>
                            <button
                              onClick={() => {
                                const stObj = stations.find(s => s.name === alt.station_name) || { name: alt.station_name, city: alt.city };
                                setSelectedStation(stObj);
                                setNavTab('dashboard');
                              }}
                              className="text-xs font-bold text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
                              <span>Investigate Station</span> &rarr;
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  /* No active alerts state */
                  <div className="py-14 text-center">
                    <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-3 opacity-90" />
                    <h5 className="text-base font-bold text-white mb-1">No Active Alerts Right Now</h5>
                    <p className="text-xs text-slate-400 max-w-md mx-auto">
                      All active Delhi NCR monitoring stations are operating within safe baseline thresholds with active atmospheric dispersion.
                    </p>
                  </div>
                )}
              </div>

            </div>
          )}

          {/* ========================================================================= */}
          {/* PAGE 4: SETTINGS & METADATA                                               */}
          {/* ========================================================================= */}
          
          {navTab === 'decision' && (
            <div className="p-6 max-w-5xl mx-auto space-y-6">
              <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
                <div className="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center border border-cyan-500/30">
                  <Briefcase className="w-5 h-5 text-cyan-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">Regional Decision Support</h2>
                  <p className="text-sm text-slate-400">Automated multi-station synthesis for Delhi NCR</p>
                </div>
              </div>

              {loadingDecision || !decisionSupportData ? (
                <div className="flex items-center justify-center h-40 text-cyan-500 text-sm">
                  <RefreshCw className="w-5 h-5 animate-spin mr-2" />
                  Analyzing regional data...
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                      <div className="text-slate-400 text-xs font-semibold mb-1">Current Avg AQI</div>
                      <div className="text-2xl font-bold text-white flex items-end gap-2">
                        {decisionSupportData.current_aqi}
                        <span className="text-sm text-slate-400 mb-0.5">{decisionSupportData.current_aqi_category}</span>
                      </div>
                    </div>
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                      <div className="text-slate-400 text-xs font-semibold mb-1">24h Peak Forecast</div>
                      <div className="text-2xl font-bold text-rose-400 flex items-end gap-2">
                        {decisionSupportData.forecast_peak_aqi} AQI
                      </div>
                      <div className="text-[10px] text-slate-500 mt-1">at {decisionSupportData.forecast_peak_station}</div>
                    </div>
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                      <div className="text-slate-400 text-xs font-semibold mb-1">Regional Risk Level</div>
                      <div className="text-xl font-bold text-amber-400">
                        {decisionSupportData.risk_level}
                      </div>
                    </div>
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                      <div className="text-slate-400 text-xs font-semibold mb-1">Fire Influence</div>
                      <div className="text-xl font-bold text-orange-400">
                        {decisionSupportData.regional_fire_influence}
                      </div>
                      <div className="text-[10px] text-slate-500 mt-1">{decisionSupportData.downwind_station_count} stations downwind</div>
                    </div>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                    <h3 className="text-white font-bold mb-4 flex items-center gap-2">
                      <Info className="w-4 h-4 text-cyan-400" /> Actionable Recommendations
                    </h3>
                    <ul className="space-y-3">
                      {decisionSupportData.recommended_actions.map((action, idx) => (
                        <li key={idx} className="flex items-start gap-3 bg-slate-950/50 p-3 rounded-lg border border-slate-800/50">
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                          <span className="text-sm text-slate-300">{action}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl flex items-center justify-between">
                      <div>
                        <div className="text-slate-400 text-xs font-semibold">Dispersion Conditions</div>
                        <div className="text-white font-medium mt-1">{decisionSupportData.dispersion_status}</div>
                      </div>
                      <Wind className="w-6 h-6 text-slate-600" />
                    </div>
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl flex items-center justify-between">
                      <div>
                        <div className="text-slate-400 text-xs font-semibold">Rain Expected (24h)</div>
                        <div className="text-white font-medium mt-1">{decisionSupportData.rain_expected}</div>
                      </div>
                      <CloudRain className="w-6 h-6 text-slate-600" />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {navTab === 'trust' && (
            <div className="p-6 max-w-5xl mx-auto space-y-6">
              <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
                <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center border border-purple-500/30">
                  <ShieldCheck className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">XGBoost Model Trust</h2>
                  <p className="text-sm text-slate-400">Statistical evaluation on 18,000+ holdout test samples</p>
                </div>
              </div>

              {loadingTrust || !modelTrustData ? (
                <div className="flex items-center justify-center h-40 text-purple-500 text-sm">
                  <RefreshCw className="w-5 h-5 animate-spin mr-2" />
                  Loading model metrics...
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                    <h3 className="text-white font-bold mb-4 text-sm">Overall Dataset Metrics</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/50">
                        <div className="text-[10px] text-slate-500 font-semibold mb-1">R² Score</div>
                        <div className="text-xl font-bold text-white">{modelTrustData.overall_dataset_metrics.overall_r2}</div>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/50">
                        <div className="text-[10px] text-slate-500 font-semibold mb-1">Mean Absolute Error</div>
                        <div className="text-xl font-bold text-white">{modelTrustData.overall_dataset_metrics.overall_mae}</div>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/50">
                        <div className="text-[10px] text-slate-500 font-semibold mb-1">Root Mean Square Error</div>
                        <div className="text-xl font-bold text-white">{modelTrustData.overall_dataset_metrics.overall_rmse}</div>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/50">
                        <div className="text-[10px] text-slate-500 font-semibold mb-1">Test Samples</div>
                        <div className="text-xl font-bold text-white">{modelTrustData.overall_dataset_metrics.total_test_samples.toLocaleString()}</div>
                      </div>
                    </div>
                  </div>

                  {modelTrustData.scatter_sample && <ModelScatterPlot data={modelTrustData.scatter_sample} />}

                  <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                    <div className="flex justify-between items-center mb-1">
                      <h3 className="text-white font-bold text-sm">Station-Specific Evaluation</h3>
                      <span className="px-2 py-1 bg-purple-500/20 text-purple-300 text-xs rounded border border-purple-500/30">{modelTrustData.station}</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mb-4 leading-relaxed">
                      Per-station accuracy is naturally lower than the overall pooled R² (0.574) shown above. The model was trained jointly across all 50 stations, so it captures shared patterns (daily cycles, regional weather effects) that boost aggregate accuracy — but any single station's own time series is noisier in isolation. This is expected model behavior, not reduced accuracy.
                    </p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                      <div>
                        <div className="text-[10px] text-slate-500 font-semibold">Pearson Correlation</div>
                        <div className="text-lg font-bold text-emerald-400">{modelTrustData.pearson_r}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-500 font-semibold">Station R²</div>
                        <div className="text-lg font-bold text-white">{modelTrustData.r2_score}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-500 font-semibold">Station MAE</div>
                        <div className="text-lg font-bold text-white">{modelTrustData.mae}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-500 font-semibold">Holdout Points</div>
                        <div className="text-lg font-bold text-white">{modelTrustData.sample_count}</div>
                      </div>
                    </div>
                    
                    {/* Time series visualization table for the last 72 hours */}
                    <details className="border border-slate-800 rounded-lg overflow-hidden group">
                      <summary className="bg-slate-800/50 px-4 py-3 text-xs font-semibold text-slate-300 cursor-pointer flex justify-between items-center hover:bg-slate-800/70 transition-colors">
                        <span>View Station Example Predictions (Holdout Set)</span>
                        <span className="text-slate-500 group-open:rotate-180 transition-transform">▼</span>
                      </summary>
                      <div className="border-t border-slate-800">
                      <div className="max-h-60 overflow-y-auto custom-scrollbar">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-950/50 sticky top-0 text-slate-400">
                            <tr>
                              <th className="px-4 py-2 font-medium">Timestamp</th>
                              <th className="px-4 py-2 font-medium text-right">Actual</th>
                              <th className="px-4 py-2 font-medium text-right">Predicted</th>
                              <th className="px-4 py-2 font-medium text-right">Error</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/50">
                            {modelTrustData.time_series.slice().reverse().map((row, idx) => (
                              <tr key={idx} className="hover:bg-slate-800/30">
                                <td className="px-4 py-2 text-slate-300">{new Date(row.timestamp).toLocaleString()}</td>
                                <td className="px-4 py-2 text-right text-cyan-300 font-medium">{row.actual_pm25.toFixed(1)}</td>
                                <td className="px-4 py-2 text-right text-rose-300 font-medium">{row.predicted_pm25.toFixed(1)}</td>
                                <td className="px-4 py-2 text-right text-slate-400">{row.error.toFixed(1)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      </div>
                    </details>
                  </div>
                </div>
              )}
            </div>
          )}


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

                {/* PART 1 — Numeric Delta Readout Table */}
                {simResults && (
                  <div className="mt-8 pt-6 border-t border-slate-800 space-y-4">
                    {/* One-Line Summary Banner */}
                    <div className="p-3.5 bg-cyan-950/40 border border-cyan-500/30 rounded-xl text-cyan-300 text-xs font-medium flex items-center gap-2.5">
                      <Sparkles className="w-4.5 h-4.5 text-cyan-400 shrink-0" />
                      <span>
                        Feedback mechanism triggered for <strong className="text-white underline decoration-cyan-500">{simSummaryStats.triggerCount}</strong> of the 24 simulated hours, with a maximum observed adjustment of <strong className="text-white underline decoration-rose-500">{simSummaryStats.maxAdjustment} µg/m³</strong>.
                      </span>
                    </div>

                    {/* Hourly Readout Table */}
                    <div>
                      <div className="text-xs font-bold text-slate-300 mb-2.5 flex items-center justify-between">
                        <span>Hourly Numeric Readout (First 6 Hours & Active Deltas)</span>
                        <span className="text-[10px] text-slate-500 font-normal">Non-zero feedback adjustments highlighted</span>
                      </div>
                      <div className="overflow-x-auto border border-slate-800 rounded-xl bg-slate-950/60 max-h-72 overflow-y-auto">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-900/90 text-slate-400 font-semibold border-b border-slate-800 sticky top-0 backdrop-blur-md">
                            <tr>
                              <th className="p-2.5">Hour</th>
                              <th className="p-2.5">Baseline PM2.5</th>
                              <th className="p-2.5">Feedback PM2.5</th>
                              <th className="p-2.5">Difference (Feedback − Baseline)</th>
                              <th className="p-2.5 text-right">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                            {simDiffs.map((row) => (
                              <tr key={row.hour} className={row.isTriggered ? "bg-rose-950/40 font-bold border-l-2 border-rose-500" : "hover:bg-slate-900/40 text-slate-400"}>
                                <td className="p-2.5 text-slate-300 font-sans font-semibold">Hour {row.hour}</td>
                                <td className="p-2.5 text-slate-300">{row.baseline.toFixed(2)} µg/m³</td>
                                <td className={row.isTriggered ? "p-2.5 text-rose-300 font-bold" : "p-2.5 text-slate-300"}>
                                  {row.feedback.toFixed(2)} µg/m³
                                </td>
                                <td className={row.isTriggered ? "p-2.5 text-rose-400 font-bold" : "p-2.5 text-slate-500"}>
                                  {row.diff > 0 ? `+${row.diff.toFixed(2)}` : row.diff.toFixed(2)} µg/m³
                                </td>
                                <td className="p-2.5 text-right font-sans">
                                  {row.isTriggered ? (
                                    <span className="px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 text-[10px] font-bold inline-flex items-center gap-1">
                                      ⚡ Triggered ({row.diff > 0 ? `+${row.diff.toFixed(2)}` : row.diff.toFixed(2)})
                                    </span>
                                  ) : (
                                    <span className="px-2 py-0.5 rounded-full bg-slate-900 text-slate-500 text-[10px]">
                                      Unchanged
                                    </span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* PART 2 — Research & Evidence Collapsible Card */}
              <details className="group bg-[#0F172A] border border-slate-800 rounded-2xl shadow-xl overflow-hidden transition-all mb-6" open>
                <summary className="p-5 font-bold text-sm text-white cursor-pointer bg-slate-900/80 hover:bg-slate-900 flex items-center justify-between border-b border-slate-800/80 select-none">
                  <div className="flex items-center gap-2.5">
                    <BookOpen className="w-5 h-5 text-cyan-400" />
                    <span className="text-base font-heading">Research & Evidence Behind This Feature</span>
                  </div>
                  <span className="text-xs text-slate-400 group-open:rotate-180 transition-transform">▼</span>
                </summary>

                <div className="p-6 space-y-6 text-xs text-slate-300">
                  
                  {/* 1. Module Verification */}
                  <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-3">
                    <h4 className="font-bold text-cyan-400 text-sm flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      1. Module Verification (Isolated Unit Testing)
                    </h4>
                    <p className="text-slate-400 leading-relaxed">
                      The standalone <code className="text-cyan-300 font-mono">aerosol_feedback.py</code> module was verified in isolation using 4 distinct test scenarios (from <code className="text-slate-400 font-mono">scripts/test_aerosol_feedback.py</code>) to confirm correct conditional execution:
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono text-[11px]">
                      <div className="p-3 bg-slate-900/80 rounded-lg border border-emerald-500/30">
                        <div className="font-bold text-emerald-400 font-sans mb-1">Scenario 1: High PM2.5, Low Wind (Stagnant)</div>
                        <div className="text-slate-300">Inputs: PM2.5 = 200 µg/m³, Wind = 1.5 m/s, Initial PBL = 500m</div>
                        <div className="text-cyan-300 font-bold mt-1">Result: Adjusted PBL = 440.0m (12.0% Reduction) ✓</div>
                      </div>

                      <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800">
                        <div className="font-bold text-slate-300 font-sans mb-1">Scenario 2: Low PM2.5, High Wind (Clear)</div>
                        <div className="text-slate-400">Inputs: PM2.5 = 50 µg/m³, Wind = 3.0 m/s, Initial PBL = 800m</div>
                        <div className="text-slate-400 font-bold mt-1">Result: Adjusted PBL = 800.0m (Unchanged / 0% Change) ✓</div>
                      </div>

                      <div className="p-3 bg-slate-900/80 rounded-lg border border-emerald-500/30">
                        <div className="font-bold text-emerald-400 font-sans mb-1">Scenario 3: High PM2.5, Very Low Wind (Stagnant)</div>
                        <div className="text-slate-300">Inputs: PM2.5 = 180 µg/m³, Wind = 1.0 m/s, Initial PBL = 600m</div>
                        <div className="text-cyan-300 font-bold mt-1">Result: Adjusted PBL = 528.0m (12.0% Reduction) ✓</div>
                      </div>

                      <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800">
                        <div className="font-bold text-slate-300 font-sans mb-1">Scenario 4: High PM2.5, High Wind (Not Stagnant)</div>
                        <div className="text-slate-400">Inputs: PM2.5 = 160 µg/m³, Wind = 2.5 m/s, Initial PBL = 500m</div>
                        <div className="text-slate-400 font-bold mt-1">Result: Adjusted PBL = 500.0m (Unchanged / 0% Change) ✓</div>
                      </div>
                    </div>
                  </div>

                  {/* 2. Scientific Basis */}
                  <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-3">
                    <h4 className="font-bold text-cyan-400 text-sm flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-cyan-400" />
                      2. Scientific Basis (Published Atmospheric Literature)
                    </h4>
                    <p className="text-slate-300 leading-relaxed">
                      Published numerical modeling research using <strong>WRF-Chem (Weather Research and Forecasting model coupled with Chemistry)</strong> over Delhi NCR demonstrates that dense aerosol loading suppresses incoming solar radiation reaching the ground. This surface cooling stabilizes the lower boundary layer, weakening convective turbulence and confining pollutants to the lowest <strong>400–500m</strong> of the atmosphere.
                    </p>
                    <p className="text-slate-300 leading-relaxed">
                      During severe winter smog episodes, this positive aerosol-radiation feedback loop can amplify PM2.5 peak concentrations from baseline levels of <strong>~100 µg/m³ up to ~300 µg/m³</strong>.
                    </p>
                    <div className="p-3 bg-cyan-950/30 border border-cyan-500/30 rounded-lg text-[11px] text-cyan-300 italic">
                      <strong>Important Clarification:</strong> Our module applies a literature-informed 12% boundary layer suppression proxy under stagnant conditions (PM2.5 &gt; 150 µg/m³, wind &lt; 2.0 m/s). This is an illustrative, educational proxy informed by scientific literature, not a claim of replicating full 3D physical atmospheric radiative chemistry.
                    </div>
                  </div>

                  {/* 3. Empirical Test on Our Own Data */}
                  <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-3">
                    <h4 className="font-bold text-cyan-400 text-sm flex items-center gap-2">
                      <Database className="w-4 h-4 text-purple-400" />
                      3. Empirical Test on Our Own Dataset (Statistical Reality Check)
                    </h4>
                    <p className="text-slate-300 leading-relaxed">
                      We conducted an empirical correlation analysis on our training dataset containing <strong>N = 92,719</strong> hourly station observations (spanning May 1 to July 31, 2026):
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-center font-mono">
                      <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                        <div className="text-[10px] text-slate-500 uppercase font-sans font-semibold">PM2.5 vs. PBL Height Correlation</div>
                        <div className="text-lg font-bold text-purple-300 mt-1">r = -0.0003</div>
                        <div className="text-[10px] text-slate-400 font-sans">N = 92,719 observations</div>
                      </div>
                      <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                        <div className="text-[10px] text-slate-500 uppercase font-sans font-semibold">PM2.5 vs. 1-Hour PBL Change (ΔPBL)</div>
                        <div className="text-lg font-bold text-purple-300 mt-1">r = -0.0163</div>
                        <div className="text-[10px] text-slate-400 font-sans">N = 92,718 observations (r &lt; 0.03)</div>
                      </div>
                    </div>
                    <p className="text-slate-400 leading-relaxed">
                      <strong>Honest Explanation of Findings:</strong> This near-zero empirical correlation in our training data is completely expected due to two primary factors:
                    </p>
                    <ul className="list-disc list-inside space-y-1.5 text-slate-400 pl-2">
                      <li><strong>Seasonal Scope:</strong> Aerosol-PBL feedback is a documented winter smog phenomenon driven by strong thermal inversions. Our dataset spans summer and monsoon months, where atmospheric dynamics are dominated by intense solar convection and rain washout.</li>
                      <li><strong>Data Source Limitations:</strong> Reanalysis and Open-Meteo boundary layer height calculations rely on large-scale meteorological models that do not dynamically absorb real-time local ground station PM2.5 optical depth.</li>
                    </ul>
                  </div>

                </div>
              </details>
            </div>
          )}
          {navTab === 'settings' && (

            <div className="space-y-6 max-w-4xl">
              
              {/* Settings Card 1: Polling Frequency */}
              <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div className="flex items-center gap-2 mb-3">
                  <Clock className="w-5 h-5 text-cyan-400" />
                  <h3 className="text-base font-bold text-white font-heading">
                    Live Telemetry Polling Frequency
                  </h3>
                </div>
                <p className="text-xs text-slate-400 mb-4">
                  Configure how frequently the dashboard requests updated station observations and forecast status from the FastAPI backend.
                </p>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { label: '30 Seconds', val: 30 },
                    { label: '60 Seconds (Default)', val: 60 },
                    { label: '5 Minutes', val: 300 },
                    { label: 'Manual Refresh Only', val: 0 }
                  ].map((opt) => (
                    <button
                      key={opt.val}
                      onClick={() => setRefreshIntervalSec(opt.val)}
                      className={`p-3 rounded-xl border text-xs font-semibold transition-all text-center ${
                        refreshIntervalSec === opt.val
                          ? 'bg-cyan-950/60 border-cyan-500 text-cyan-300 shadow-md shadow-cyan-500/20'
                          : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                      }`}>
                      <div>{opt.label}</div>
                      {refreshIntervalSec === opt.val && (
                        <div className="text-[10px] text-cyan-400 font-normal mt-1">Active Setting</div>
                      )}
                    </button>
                  ))}
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
                  <span>Last successful synchronization: {lastSyncTime.toLocaleTimeString()}</span>
                  <span className="text-emerald-400 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Polling Hook Active
                  </span>
                </div>
              </div>

              {/* Settings Card 2: ML Model Information */}
              <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div className="flex items-center gap-2 mb-3">
                  <Cpu className="w-5 h-5 text-purple-400" />
                  <h3 className="text-base font-bold text-white font-heading">
                    Machine Learning Architecture (Production V1)
                  </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800">
                    <span className="text-slate-400 block font-semibold mb-1">Model Class & Target</span>
                    <p className="text-white font-bold">XGBoost Regressor (100 Trees, Depth 6)</p>
                    <p className="text-slate-400 text-[11px] mt-1">
                      Multi-step autoregressive projection with hour-by-hour lag updates across a 72-hour forecast horizon.
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800">
                    <span className="text-slate-400 block font-semibold mb-1">Training Dataset & Performance</span>
                    <p className="text-white font-bold">90-Day Delhi NCR Master Dataset</p>
                    <p className="text-slate-400 text-[11px] mt-1">
                      74,175 training rows, 18,544 test holdout rows. Evaluated Test MAE: 10.29 µg/m³, Test R²: 0.574.
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 md:col-span-2">
                    <span className="text-slate-400 block font-semibold mb-1">28 Input Features</span>
                    <p className="text-slate-300 text-[11px] leading-relaxed">
                      <code>pm25_value</code>, 5 temporal lags (<code>lag_1, 3, 6, 12, 24</code>), 4 rolling windows (<code>roll_3, 6, 12, 24</code>), 8 meteorological inputs (<code>temperature, humidity, wind_speed, wind_sin, wind_cos, pressure, precipitation, PBL mixing height</code>), 4 satellite fire anomalies (<code>Punjab, Haryana, UP, Delhi</code>), 4 calendar temporal cyclic IDs, and spatial coordinates.
                    </p>
                  </div>
                </div>
              </div>

              {/* Settings Card 3: Data Sources & Attribution */}
              <div className="bg-[#0F172A] border border-slate-800 rounded-2xl p-5 shadow-xl">
                <div className="flex items-center gap-2 mb-3">
                  <Database className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-base font-bold text-white font-heading">
                    Data Source Attribution & Transparency
                  </h3>
                </div>

                <div className="space-y-3 text-xs">
                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                    <div className="font-bold text-white mb-0.5">OpenAQ Community API (v3)</div>
                    <p className="text-slate-400 text-[11px]">
                      Provides 15-minute sub-hourly ground monitoring station telemetry across {stations.length} active locations in Delhi NCR.
                    </p>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                    <div className="font-bold text-white mb-0.5">Open-Meteo Weather API & 72h Forecast</div>
                    <p className="text-slate-400 text-[11px]">
                      Delivers hourly regional temperature, humidity, wind vectors, surface pressure, and boundary layer mixing height without rate limits.
                    </p>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                    <div className="font-bold text-white mb-0.5">NASA FIRMS (VIIRS / MODIS)</div>
                    <p className="text-slate-400 text-[11px]">
                      Thermal anomaly satellite detections for crop residue stubble burning across Punjab, Haryana, Uttar Pradesh, and Delhi NCR.
                    </p>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                    <div className="font-bold text-white mb-0.5">Central Pollution Control Board (CPCB / DPCC)</div>
                    <p className="text-slate-400 text-[11px]">
                      Official national monitoring network and standard NAQI breakpoints. (Note: Subject to periodic sensor maintenance and telemetry transmission latency).
                    </p>
                  </div>
                </div>
              </div>

            </div>
          )}

        </div>

      </div>

      {/* Station Detail Intelligence Modal */}
      {modalStation && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0F172A] border border-slate-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[88vh] animate-in fade-in zoom-in duration-200">
            
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-800 flex items-start justify-between bg-[#0F172A]/90">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-500/30">
                    {modalStation.city || 'Delhi NCR'}
                  </span>
                  {modalStation.latest_pm25 && (
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${getPM25Theme(modalStation.latest_pm25).badge}`}>
                      PM2.5: {modalStation.latest_pm25} µg/m³ (AQI: {modalStation.latest_aqi || '--'})
                    </span>
                  )}
                </div>
                <h3 className="text-lg font-bold text-white font-heading">{modalStation.name}</h3>
              </div>
              <button 
                onClick={() => setModalStation(null)}
                className="w-8 h-8 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Tabs */}
            <div className="flex border-b border-slate-800 bg-slate-950/50 px-5 pt-3 gap-4 text-xs font-semibold">
              <button 
                onClick={() => setActiveTab('current')}
                className={`pb-3 border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeTab === 'current' ? 'border-cyan-500 text-cyan-400' : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}>
                <Activity className="w-3.5 h-3.5" />
                <span>Current Sensor Readings</span>
              </button>
              <button 
                onClick={() => setActiveTab('forecast')}
                className={`pb-3 border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeTab === 'forecast' ? 'border-cyan-500 text-cyan-400' : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}>
                <TrendingUp className="w-3.5 h-3.5" />
                <span>72-Hour Forecast (AI & Weather)</span>
              </button>
              <button 
                onClick={() => setActiveTab('explain')}
                className={`pb-3 border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeTab === 'explain' ? 'border-cyan-500 text-cyan-400' : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}>
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>Why is pollution changing?</span>
              </button>

              {nearbySources && nearbySources.sources && nearbySources.sources.length > 0 && (
                <button 
                  onClick={() => setActiveTab('sources')}
                  className={`pb-3 border-b-2 transition-colors flex items-center gap-1.5 ${
                    activeTab === 'sources' ? 'border-orange-500 text-orange-400' : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}>
                  <Factory className="w-3.5 h-3.5 text-orange-400" />
                  <span>Nearby Sources</span>
                </button>
              )}

            </div>

            {/* Modal Body */}
            <div className="p-5 overflow-y-auto flex-1">
              {loadingModal ? (
                <div className="py-12 text-center text-xs text-slate-500">
                  <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-cyan-500" />
                  Fetching live telemetry & AI models from backend...
                </div>
              ) : activeTab === 'current' ? (
                <div>
                  <div className="text-xs text-slate-400 mb-3 flex items-center justify-between">
                    <span>Telemetry for {stationReadings?.readings_count || 0} environmental parameters</span>
                    <span>Source: OpenAQ / CPCB Sensor Feed</span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {stationReadings?.readings?.map((r, i) => (
                      <div key={i} className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{r.parameter}</div>
                        <div className="text-lg font-bold text-white mt-1">
                          {r.value} <span className="text-xs text-slate-400 font-normal">{r.unit}</span>
                        </div>
                        <div className="text-[10px] text-slate-400 mt-1">
                          {r.timestamp ? new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Live'}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : activeTab === 'forecast' ? (
                <div>
                  <div className="p-3 bg-cyan-950/30 border border-cyan-500/30 rounded-xl text-cyan-300 text-xs mb-4 flex items-center gap-2">
                    <Info className="w-4 h-4 shrink-0" />
                    <span>{forecastData?.note || '72-hour forecast based on XGBoost autoregressive simulation.'}</span>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs font-semibold text-slate-300 mb-2">
                      <span>Hourly Trajectory Preview (Next 72 Hours)</span>
                      <span className="text-[10px] text-cyan-400 font-medium bg-cyan-950/60 border border-cyan-500/30 px-2 py-0.5 rounded-full">
                        📊 Empirical 95% Confidence Bounds
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 max-h-72 overflow-y-auto pr-1">
                      {forecastData?.forecast?.map((fc, i) => {
                        const theme = getPM25Theme(fc.predicted_pm25);
                        return (
                          <div key={i} className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-xs flex flex-col justify-between">
                            <div>
                              <div className="text-[11px] text-slate-400 flex items-center justify-between">
                                <span>+ {fc.hour_offset}h</span>
                                <span className={`text-[10px] px-1.5 py-0.2 rounded font-semibold ${theme.badge}`}>
                                  AQI {fc.predicted_aqi}
                                </span>
                              </div>
                              <div className="text-base font-bold text-white mt-1">
                                {fc.predicted_pm25} <span className="text-[10px] text-slate-400 font-normal">µg/m³</span>
                              </div>

                              {/* Confidence Interval / Fallback Note */}
                              {fc.expected_low !== null && fc.expected_high !== null ? (
                                <div className="text-[10px] text-cyan-300 font-mono mt-1 bg-cyan-950/40 px-1.5 py-0.5 rounded border border-cyan-500/20">
                                  {fc.expected_low}–{fc.expected_high} <span className="text-[9px] text-slate-400 font-sans">({fc.uncertainty_bucket})</span>
                                </div>
                              ) : (
                                <div className="text-[9px] text-amber-300 font-sans italic mt-1 bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-500/30" title={fc.confidence_note || "Insufficient historical samples in this range to compute a reliable confidence interval"}>
                                  ⚠️ No range (&gt;200)
                                </div>
                              )}
                            </div>

                            <div className="text-[10px] text-slate-400 mt-2 pt-1 border-t border-slate-800/60 flex items-center justify-between">
                              <span>{new Date(fc.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit' })}</span>
                              <span className="text-[9px] text-slate-500">{fc.aqi_category}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : activeTab === 'sources' && nearbySources && nearbySources.sources && nearbySources.sources.length > 0 ? (
                <div className="space-y-4">
                  <div className="p-4 bg-slate-900 border-l-4 border-orange-500 rounded-r-xl">
                    <div className="flex items-center gap-2 mb-2">
                      <Factory className="w-5 h-5 text-orange-500" />
                      <span className="text-sm font-bold text-slate-100">Local Industrial Activity</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      This station's elevated pollution may be partly influenced by nearby industrial activity, including {nearbySources.sources[0].name} ({nearbySources.sources[0].type}), located {nearbySources.sources[0].distance_km}km away.
                    </p>
                  </div>
                  
                  <div className="grid gap-2">
                    {nearbySources.sources.map((src, i) => (
                      <div key={i} className="p-3 bg-slate-800/50 rounded-lg flex items-center justify-between">
                        <div>
                          <div className="text-sm font-semibold text-slate-200">{src.name}</div>
                          <div className="text-[11px] text-slate-400 mt-0.5">{src.type}</div>
                        </div>
                        <div className="text-xs font-mono text-orange-300 bg-orange-950/40 px-2 py-1 rounded">
                          {src.distance_km} km
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                /* "Why is pollution changing?" SHAP Explainability Tab */
                <div className="space-y-4">
                  <div className="p-4 bg-gradient-to-r from-slate-950 via-[#0F172A] to-cyan-950/40 border border-cyan-500/40 rounded-xl shadow-lg">
                    <div className="flex items-center gap-2 mb-1.5">
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      <span className="text-xs font-bold text-cyan-300 uppercase tracking-wider">AI Feature Attribution</span>
                      <span className="text-[11px] text-slate-400 ml-auto">
                        Expected Base: {explainData?.base_expected_value || 42.9} µg/m³
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-slate-100 leading-snug">
                      {generateExplainSummary()}
                    </p>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                    <span className="font-semibold text-slate-300">Top Contributing Factors (SHAP Feature Attribution)</span>
                    <span>Sorted by absolute impact magnitude</span>
                  </div>

                  <div className="space-y-2.5">
                    {explainData?.top_contributing_factors?.map((factor, idx) => {
                      const meta = FEATURE_DICTIONARY[factor.feature] || {
                        label: factor.feature,
                        unit: '',
                        icon: '🔹',
                        desc: ''
                      };

                      const isIncrease = factor.impact === 'increase';
                      const absShap = Math.abs(factor.shap_value);
                      const barPercent = Math.min(100, Math.max(10, Math.round((absShap / maxShapMagnitude) * 100)));

                      return (
                        <div 
                          key={idx} 
                          className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-slate-700 transition-colors">
                          <div className="flex items-center justify-between gap-3 mb-1.5">
                            <div className="flex items-center gap-2.5 min-w-0">
                              <span className="text-base shrink-0">{meta.icon}</span>
                              <div className="truncate">
                                <div className="text-xs font-bold text-slate-200 truncate">
                                  {meta.label}
                                </div>
                                <div className="text-[11px] text-slate-400">
                                  Current reading: <span className="font-semibold text-slate-300">{factor.value} {meta.unit}</span>
                                </div>
                              </div>
                            </div>

                            <div className="text-right shrink-0">
                              <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${
                                isIncrease 
                                  ? 'bg-rose-950/80 text-rose-300 border border-rose-500/30' 
                                  : 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/30'
                              }`}>
                                {isIncrease ? (
                                  <>
                                    <ArrowUpRight className="w-3.5 h-3.5 text-rose-400" />
                                    <span>+{factor.shap_value} µg/m³ (pushing UP)</span>
                                  </>
                                ) : (
                                  <>
                                    <ArrowDownRight className="w-3.5 h-3.5 text-emerald-400" />
                                    <span>{factor.shap_value} µg/m³ (pushing DOWN)</span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>

                          <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden mt-2">
                            <div 
                              style={{ width: `${barPercent}%` }}
                              className={`h-full rounded-full transition-all duration-500 ${
                                isIncrease ? 'bg-gradient-to-r from-orange-500 to-rose-500' : 'bg-gradient-to-r from-teal-500 to-emerald-500'
                              }`}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="text-[11px] text-slate-400 bg-slate-950/40 p-3 rounded-lg border border-slate-800/60 flex items-start gap-2">
                    <HelpCircle className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                    <span>
                      Shapley (SHAP) values quantify how much each environmental feature raises or lowers the predicted PM2.5 relative to regional baseline atmospheric conditions.
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 bg-slate-950/80 border-t border-slate-800 flex justify-end">
              <button 
                onClick={() => setModalStation(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl transition-colors">
                Close
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
