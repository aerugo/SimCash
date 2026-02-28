import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import 'katex/dist/katex.min.css';

import { API_ORIGIN } from '../api';
import { CostComparisonChart, ComplexCostDeltaChart, SettlementDegradationChart } from '../components/PaperChart';
const API_BASE = `${API_ORIGIN}/api`;

interface DocPage {
  id: string;
  title: string;
  icon: string;
  category: string;
  order: number;
  date?: string;
  paper?: string;
  paper_title?: string;
}

interface DocContent extends DocPage {
  content: string;
}

interface NavGroup {
  key: string;
  label: string;
}

const GROUPS: NavGroup[] = [
  { key: 'guide', label: 'Guides' },
  { key: 'research', label: 'Research' },
  { key: 'paper', label: 'Research Papers' },
  { key: 'advanced', label: 'Advanced Topics' },
  { key: 'blog', label: 'Blog Posts' },
  { key: 'reference', label: 'Reference' },
];

// Chart registry — maps chart IDs to React components
const CHART_COMPONENTS: Record<string, React.FC> = {
  'cost-comparison': CostComparisonChart,
  'complex-cost-delta': ComplexCostDeltaChart,
  'settlement-degradation': SettlementDegradationChart,
};

// Replace <!-- CHART: xxx --> comments with renderable divs
function preprocessCharts(md: string): string {
  return md.replace(
    /<!--\s*CHART:\s*(\S+)\s*-->/g,
    '<div data-chart="$1"></div>'
  );
}

// Custom markdown components for dark theme styling
const markdownComponents: Components = {
  div: ({ node, children, ...props }) => {
    const chartId = (props as Record<string, unknown>)['data-chart'] as string | undefined;
    if (chartId && CHART_COMPONENTS[chartId]) {
      const ChartComponent = CHART_COMPONENTS[chartId];
      return <div className="my-6"><ChartComponent /></div>;
    }
    return <div {...props}>{children}</div>;
  },
  h1: ({ children }) => (
    <h1 className="text-2xl font-bold text-slate-100 mb-1">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold text-slate-200 mt-8 mb-3">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-medium text-slate-300 mt-6 mb-2">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-sm font-medium text-slate-300 mt-4 mb-2">{children}</h4>
  ),
  p: ({ children }) => {
    return <p className="text-slate-300 leading-relaxed mb-4">{children}</p>;
  },
  blockquote: ({ children }) => {
    // Detect callout type from content
    const text = String(children);
    let borderClass = 'border-sky-500/30 bg-sky-500/5';
    if (text.includes('⚠️')) {
      borderClass = 'border-amber-500/30 bg-amber-500/5';
    } else if (text.includes('💡')) {
      borderClass = 'border-violet-500/30 bg-violet-500/5';
    }
    return (
      <div className={`border-l-4 rounded-r-lg p-4 my-4 text-sm ${borderClass} [&>p]:mb-0`}>
        {children}
      </div>
    );
  },
  ul: ({ children }) => (
    <ul className="list-disc pl-5 space-y-1 mb-4 text-slate-300">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-5 space-y-1 mb-4 text-slate-300">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="text-slate-300">{children}</li>
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-sky-400 hover:underline">
      {children}
    </a>
  ),
  code: ({ className, children }) => {
    const isBlock = className?.includes('language-') || String(children).includes('\n');
    if (isBlock) {
      return (
        <pre className="bg-slate-900 border border-slate-700 rounded-lg p-4 text-xs font-mono text-slate-300 overflow-x-auto my-4 whitespace-pre">
          <code>{children}</code>
        </pre>
      );
    }
    return (
      <code className="text-sky-400 bg-slate-800 px-1 py-0.5 rounded text-xs">{children}</code>
    );
  },
  pre: ({ children }) => (
    <>{children}</>
  ),
  table: ({ children }) => (
    <table className="w-full text-sm border-collapse mb-4">{children}</table>
  ),
  thead: ({ children }) => (
    <thead>{children}</thead>
  ),
  th: ({ children }) => (
    <th className="text-left py-2 text-slate-300 border-b border-slate-700">{children}</th>
  ),
  td: ({ children }) => {
    const text = String(children);
    const isCode = text.startsWith('`') && text.endsWith('`');
    return (
      <td className={`py-1.5 pr-4 text-sm border-b border-slate-800 ${isCode ? 'font-mono text-sky-400' : 'text-slate-400'}`}>
        {children}
      </td>
    );
  },
  tr: ({ children }) => (
    <tr className="border-b border-slate-800">{children}</tr>
  ),
  strong: ({ children }) => (
    <strong className="text-slate-200 font-semibold">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="text-slate-300 italic">{children}</em>
  ),
  hr: () => (
    <hr className="border-slate-700 my-6" />
  ),
  img: ({ src, alt }) => {
    const resolvedSrc = src?.startsWith('/api/') ? `${API_ORIGIN}${src}` : src;
    return (
      <img src={resolvedSrc} alt={alt || ''} className="max-w-full rounded-lg my-4 border border-slate-700" loading="lazy" />
    );
  },
  details: ({ children }) => (
    <details className="my-4 border border-slate-700 rounded-lg overflow-hidden">
      {children}
    </details>
  ),
  summary: ({ children }) => (
    <summary className="cursor-pointer px-4 py-2 bg-slate-800 text-slate-300 hover:bg-slate-700 text-sm font-medium">
      {children}
    </summary>
  ),
};

export function DocsView() {
  const params = useParams<{ '*': string }>();
  const slug = params['*'] || undefined;
  const navigate = useNavigate();
  const [pages, setPages] = useState<DocPage[]>([]);
  const [activeId, setActiveId] = useState<string>(slug || 'overview');
  const [content, setContent] = useState<string>('');
  const [activeMeta, setActiveMeta] = useState<DocContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingContent, setLoadingContent] = useState(false);
  const cache = useRef<Record<string, DocContent>>({});

  // Sync URL slug to activeId
  useEffect(() => {
    if (slug && slug !== activeId) {
      setActiveId(slug);
    }
  }, [slug]);

  // Fetch page list on mount
  useEffect(() => {
    fetch(`${API_BASE}/docs`)
      .then(r => r.json())
      .then(data => {
        setPages(data.pages);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Fetch content when active page changes
  const fetchContent = useCallback((id: string) => {
    if (cache.current[id]) {
      const cached = cache.current[id];
      setContent(cached.content);
      setActiveMeta(cached);
      return;
    }
    setLoadingContent(true);
    fetch(`${API_BASE}/docs/${id}`)
      .then(r => r.json())
      .then((data: DocContent) => {
        cache.current[id] = data;
        setContent(data.content);
        setActiveMeta(data);
        setLoadingContent(false);
      })
      .catch(() => {
        setContent('# Error\n\nFailed to load documentation.');
        setLoadingContent(false);
      });
  }, []);

  useEffect(() => {
    if (activeId) fetchContent(activeId);
  }, [activeId, fetchContent]);

  const groupedPages = GROUPS.map(g => ({
    ...g,
    items: pages.filter(p => p.category === g.key).sort((a, b) => a.order - b.order),
  }));

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-400" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Mobile nav — grouped with optgroup for papers */}
      <div className="md:hidden mb-4">
        <select
          value={activeId}
          onChange={e => { setActiveId(e.target.value); navigate(`/docs/${e.target.value}`); }}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200"
        >
          {groupedPages.map(g => {
            if (g.items.length === 0) return null;
            if (g.key === 'paper') {
              // Group papers by paper slug
              const paperGroups: Record<string, { title: string; items: DocPage[] }> = {};
              for (const item of g.items) {
                const key = item.paper || 'other';
                if (!paperGroups[key]) paperGroups[key] = { title: item.paper_title || key, items: [] };
                paperGroups[key].items.push(item);
              }
              return Object.entries(paperGroups).map(([pKey, pg]) => (
                <optgroup key={pKey} label={`📑 ${pg.title}`}>
                  {pg.items.map(item => (
                    <option key={item.id} value={item.id}>{item.icon} {item.title}</option>
                  ))}
                </optgroup>
              ));
            }
            return (
              <optgroup key={g.key} label={g.label}>
                {g.items.map(item => (
                  <option key={item.id} value={item.id}>{item.icon} {item.title}</option>
                ))}
              </optgroup>
            );
          })}
        </select>
      </div>

      <div className="flex gap-6">
      {/* Sidebar */}
      <nav className="w-56 shrink-0 hidden md:block">
        <div className="sticky top-24 space-y-5">
          {groupedPages.map(g => {
            // For paper category, group by paper slug
            if (g.key === 'paper' && g.items.length > 0) {
              const paperGroups: Record<string, { title: string; items: DocPage[] }> = {};
              for (const item of g.items) {
                const key = item.paper || 'other';
                if (!paperGroups[key]) paperGroups[key] = { title: item.paper_title || key, items: [] };
                paperGroups[key].items.push(item);
              }
              return (
                <div key={g.key}>
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">{g.label}</h4>
                  {Object.entries(paperGroups).map(([pKey, pg]) => (
                    <div key={pKey} className="mb-3">
                      <h5 className="text-[11px] font-semibold text-slate-400 px-3 mb-1">{pg.title}</h5>
                      <div className="space-y-0.5">
                        {pg.items.map(item => (
                          <button
                            key={item.id}
                            onClick={() => { setActiveId(item.id); navigate(`/docs/${item.id}`); window.scrollTo(0, 0); }}
                            className={`w-full text-left px-3 py-1.5 rounded-lg text-sm transition-colors pl-5 ${
                              activeId === item.id
                                ? 'bg-sky-500/10 text-sky-400'
                                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                            }`}
                          >
                            <span className="mr-2">{item.icon}</span>
                            {item.title}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              );
            }
            return (
              <div key={g.key}>
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">{g.label}</h4>
                <div className="space-y-0.5">
                  {g.items.map(item => (
                    <button
                      key={item.id}
                      onClick={() => { setActiveId(item.id); navigate(`/docs/${item.id}`); window.scrollTo(0, 0); }}
                      className={`w-full text-left px-3 py-1.5 rounded-lg text-sm transition-colors ${
                        activeId === item.id
                          ? 'bg-sky-500/10 text-sky-400'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                      }`}
                    >
                      <span className="mr-2">{item.icon}</span>
                      {item.title}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </nav>

      {/* Content */}
      <article className="flex-1 min-w-0 overflow-x-hidden">
        {loadingContent ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-sky-400" />
          </div>
        ) : (
          <div>
            {activeMeta?.category === 'blog' && (
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs bg-violet-500/20 text-violet-400 px-2 py-0.5 rounded-full">Blog</span>
                {activeMeta.date && <span className="text-xs text-slate-500">{activeMeta.date}</span>}
              </div>
            )}
            {/* Paper header: title, ToC, section title */}
            {(() => {
              const paperSlug = activeMeta?.paper;
              if (!paperSlug || !activeMeta) return null;
              const siblings = pages
                .filter(p => p.paper === paperSlug)
                .sort((a, b) => a.order - b.order);
              if (siblings.length < 2) return null;
              return (
                <div className="mb-6">
                  <h2 className="text-lg font-semibold text-slate-200 mb-3">{activeMeta.paper_title}</h2>
                  <div className="p-4 bg-slate-800/50 border border-slate-700 rounded-lg mb-4">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Contents</h4>
                    <ol className="space-y-1">
                      {siblings.map((s, i) => (
                        <li key={s.id}>
                          <button
                            onClick={() => { setActiveId(s.id); navigate(`/docs/${s.id}`); window.scrollTo(0, 0); }}
                            className={`text-sm transition-colors ${
                              s.id === activeId ? 'text-sky-400 font-medium' : 'text-slate-400 hover:text-sky-400'
                            }`}
                          >
                            {i + 1}. {s.icon} {s.title}
                          </button>
                        </li>
                      ))}
                    </ol>
                  </div>
                  <h3 className="text-base font-medium text-slate-300 mb-4 pb-3 border-b border-slate-800">
                    {activeMeta.icon} {activeMeta.title}
                  </h3>
                </div>
              );
            })()}
            <div className="prose prose-invert prose-sm max-w-none space-y-0">
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex, rehypeRaw]} components={markdownComponents}>
                {preprocessCharts(content)}
              </ReactMarkdown>
            </div>
            {/* Paper prev/next navigation */}
            {(() => {
              const paperSlug = activeMeta?.paper;
              if (!paperSlug) return null;
              const siblings = pages
                .filter(p => p.paper === paperSlug)
                .sort((a, b) => a.order - b.order);
              const idx = siblings.findIndex(s => s.id === activeId);
              if (idx < 0) return null;
              const prev = idx > 0 ? siblings[idx - 1] : null;
              const next = idx < siblings.length - 1 ? siblings[idx + 1] : null;
              if (!prev && !next) return null;
              return (
                <div className="flex justify-between items-center mt-10 pt-6 border-t border-slate-800">
                  {prev ? (
                    <button
                      onClick={() => { setActiveId(prev.id); navigate(`/docs/${prev.id}`); window.scrollTo(0, 0); }}
                      className="flex items-center gap-2 text-sm text-slate-400 hover:text-sky-400 transition-colors"
                    >
                      <span>←</span>
                      <span>{prev.icon} {prev.title}</span>
                    </button>
                  ) : <div />}
                  {next ? (
                    <button
                      onClick={() => { setActiveId(next.id); navigate(`/docs/${next.id}`); window.scrollTo(0, 0); }}
                      className="flex items-center gap-2 text-sm text-slate-400 hover:text-sky-400 transition-colors"
                    >
                      <span>{next.icon} {next.title}</span>
                      <span>→</span>
                    </button>
                  ) : <div />}
                </div>
              );
            })()}
          </div>
        )}
      </article>
      </div>
    </div>
  );
}
