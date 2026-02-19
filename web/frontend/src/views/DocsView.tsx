import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';

const API_BASE = '/api';

interface DocPage {
  id: string;
  title: string;
  icon: string;
  category: string;
  order: number;
  date?: string;
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
  { key: 'advanced', label: 'Advanced Topics' },
  { key: 'blog', label: 'Blog Posts' },
  { key: 'reference', label: 'Reference' },
];

// Custom markdown components for dark theme styling
const markdownComponents: Components = {
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
    // Detect callout blocks (lines starting with > emoji)
    const text = String(children);
    if (text.startsWith('ℹ️') || text.startsWith('> ℹ️')) {
      return (
        <div className="border-l-4 border-sky-500/30 bg-sky-500/5 rounded-r-lg p-4 my-4 text-sm">
          {children}
        </div>
      );
    }
    if (text.startsWith('⚠️') || text.startsWith('> ⚠️')) {
      return (
        <div className="border-l-4 border-amber-500/30 bg-amber-500/5 rounded-r-lg p-4 my-4 text-sm">
          {children}
        </div>
      );
    }
    if (text.startsWith('💡') || text.startsWith('> 💡')) {
      return (
        <div className="border-l-4 border-violet-500/30 bg-violet-500/5 rounded-r-lg p-4 my-4 text-sm">
          {children}
        </div>
      );
    }
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
};

export function DocsView() {
  const { slug } = useParams<{ slug: string }>();
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
      {/* Mobile nav */}
      <div className="md:hidden mb-4">
        <select
          value={activeId}
          onChange={e => { setActiveId(e.target.value); navigate(`/docs/${e.target.value}`); }}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200"
        >
          {pages.map(p => (
            <option key={p.id} value={p.id}>{p.icon} {p.title}</option>
          ))}
        </select>
      </div>

      <div className="flex gap-6">
      {/* Sidebar */}
      <nav className="w-56 shrink-0 hidden md:block">
        <div className="sticky top-24 space-y-5">
          {groupedPages.map(g => (
            <div key={g.key}>
              <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">{g.label}</h4>
              <div className="space-y-0.5">
                {g.items.map(item => (
                  <button
                    key={item.id}
                    onClick={() => { setActiveId(item.id); navigate(`/docs/${item.id}`); }}
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
          ))}
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
            <div className="prose prose-invert prose-sm max-w-none space-y-0">
              <ReactMarkdown components={markdownComponents}>
                {content}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </article>
      </div>
    </div>
  );
}
