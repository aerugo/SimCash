import { useEffect, useState } from 'react';
import { getSimConfig } from '../api';

export function ConfigView({ simId }: { simId: string }) {
  const [config, setConfig] = useState<{ raw_config: Record<string, unknown>; ffi_config: Record<string, unknown> } | null>(null);
  const [view, setView] = useState<'raw' | 'ffi'>('raw');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getSimConfig(simId).then(setConfig).finally(() => setLoading(false));
  }, [simId]);

  if (loading) return <div className="text-slate-500">Loading config...</div>;
  if (!config) return <div className="text-slate-500">No config available.</div>;

  const data = view === 'raw' ? config.raw_config : config.ffi_config;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">⚙️ Config Inspector</h2>
        <div className="flex gap-1 bg-slate-700 rounded-lg p-0.5">
          <button onClick={() => setView('raw')} className={`px-3 py-1 text-xs rounded ${view === 'raw' ? 'bg-sky-600 text-white' : 'text-slate-400'}`}>YAML Config</button>
          <button onClick={() => setView('ffi')} className={`px-3 py-1 text-xs rounded ${view === 'ffi' ? 'bg-sky-600 text-white' : 'text-slate-400'}`}>FFI Config</button>
        </div>
      </div>

      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
        <pre className="text-xs font-mono text-slate-300 overflow-auto max-h-[calc(100vh-16rem)] whitespace-pre-wrap">
          {renderYamlLike(data, 0)}
        </pre>
      </div>
    </div>
  );
}

function renderYamlLike(obj: unknown, indent: number): string {
  const pad = '  '.repeat(indent);
  if (obj === null || obj === undefined) return `${pad}null`;
  if (typeof obj === 'string') return `${pad}"${obj}"`;
  if (typeof obj === 'number' || typeof obj === 'boolean') return `${pad}${obj}`;
  if (Array.isArray(obj)) {
    if (obj.length === 0) return `${pad}[]`;
    return obj.map(item => {
      if (typeof item === 'object' && item !== null) {
        return `${pad}- ${renderYamlLike(item, indent + 1).trimStart()}`;
      }
      return `${pad}- ${String(item)}`;
    }).join('\n');
  }
  if (typeof obj === 'object') {
    return Object.entries(obj as Record<string, unknown>).map(([k, v]) => {
      if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
        return `${pad}${k}:\n${renderYamlLike(v, indent + 1)}`;
      }
      if (Array.isArray(v)) {
        return `${pad}${k}:\n${renderYamlLike(v, indent + 1)}`;
      }
      return `${pad}${k}: ${v === null ? 'null' : String(v)}`;
    }).join('\n');
  }
  return `${pad}${String(obj)}`;
}
