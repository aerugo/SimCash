import React, { useCallback } from 'react';
import Editor from 'react-simple-code-editor';
import { Highlight, themes } from 'prism-react-renderer';

// Add YAML language support to Prism (prism-react-renderer only ships JS/JSX/markup by default)
// We define minimal grammars inline to avoid pulling in full prismjs.

const yamlGrammar = {
  comment: /#.*/,
  string: [
    { pattern: /(["'])(?:(?!\1)[^\\\n]|\\.)*\1/, greedy: true },
  ],
  number: /\b\d+(?:\.\d+)?\b/,
  boolean: /\b(?:true|false|yes|no|null)\b/i,
  key: { pattern: /[\w.-]+(?=\s*:)/, alias: 'attr-name' },
  punctuation: /[:\-[\]{}]/,
};

const jsonGrammar = {
  string: { pattern: /"(?:[^"\\]|\\.)*"/, greedy: true },
  number: /\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b/,
  boolean: /\b(?:true|false|null)\b/,
  punctuation: /[{}[\],]/,
  operator: /:/,
};

// Custom theme tokens → Tailwind-ish colors
const customTheme = {
  ...themes.nightOwl,
  styles: [
    ...themes.nightOwl.styles,
    { types: ['attr-name'], style: { color: '#67e8f9' } },   // cyan-300
    { types: ['string'], style: { color: '#86efac' } },       // green-300
    { types: ['number'], style: { color: '#fcd34d' } },       // amber-300
    { types: ['boolean'], style: { color: '#c084fc' } },      // purple-400
    { types: ['comment'], style: { color: '#94a3b8', fontStyle: 'italic' as const } }, // slate-400
    { types: ['punctuation'], style: { color: '#94a3b8' } },
    { types: ['operator'], style: { color: '#94a3b8' } },
    { types: ['plain'], style: { color: '#e2e8f0' } },
  ],
};

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  language: 'yaml' | 'json';
  height?: string;
  className?: string;
}

export function CodeEditor({ value, onChange, language, height = '500px', className = '' }: CodeEditorProps) {
  const grammar = language === 'yaml' ? yamlGrammar : jsonGrammar;

  const highlight = useCallback((code: string) => (
    <Highlight theme={customTheme} code={code} language={language}>
      {({ tokens: prismTokens, getLineProps, getTokenProps }) => {
        // prism-react-renderer may not know yaml/json — fall back to manual tokenization
        // Check if Prism actually parsed it (more than 1 token type)
        const isParsed = prismTokens.some(line => line.some(t => t.types[0] !== 'plain'));

        if (isParsed) {
          return (
            <>
              {prismTokens.map((line, i) => (
                <div key={i} {...getLineProps({ line })}>
                  {line.map((token, j) => (
                    <span key={j} {...getTokenProps({ token })} />
                  ))}
                </div>
              ))}
            </>
          );
        }

        // Manual highlighting fallback using our grammar
        return <>{manualHighlight(code, grammar)}</>;
      }}
    </Highlight>
  ), [language, grammar]);

  return (
    <div
      className={`bg-slate-900 border border-slate-700 rounded-xl overflow-auto focus-within:border-sky-500 transition-colors ${className}`}
      style={{ height, minHeight: '200px' }}
    >
      <Editor
        value={value}
        onValueChange={onChange}
        highlight={highlight}
        padding={16}
        textareaClassName="code-editor-textarea"
        style={{
          fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
          fontSize: '0.875rem',
          lineHeight: '1.625',
          minHeight: '100%',
        }}
      />
    </div>
  );
}

// Manual tokenizer for when Prism doesn't have the language grammar
function manualHighlight(code: string, grammar: Record<string, unknown>): React.JSX.Element {
  const lines = code.split('\n');
  return (
    <>
      {lines.map((line, i) => (
        <div key={i}>{highlightLine(line, grammar)}{'\n'}</div>
      ))}
    </>
  );
}

function highlightLine(line: string, grammar: Record<string, unknown>): ( React.JSX.Element | string)[] {
  const tokens: { start: number; end: number; type: string }[] = [];

  for (const [type, pattern] of Object.entries(grammar)) {
    const patterns = Array.isArray(pattern) ? pattern : [pattern];
    for (const p of patterns) {
      const regex = p instanceof RegExp ? new RegExp(p.source, 'g') :
        (p && typeof p === 'object' && 'pattern' in p) ? new RegExp((p as { pattern: RegExp }).pattern.source, 'g') : null;
      if (!regex) continue;
      let m;
      while ((m = regex.exec(line)) !== null) {
        const actualType = (p && typeof p === 'object' && 'alias' in p) ? (p as { alias: string }).alias : type;
        tokens.push({ start: m.index, end: m.index + m[0].length, type: actualType });
      }
    }
  }

  // Sort by start, prefer longer matches
  tokens.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));

  // Remove overlapping tokens
  const filtered: typeof tokens = [];
  let lastEnd = 0;
  for (const t of tokens) {
    if (t.start >= lastEnd) {
      filtered.push(t);
      lastEnd = t.end;
    }
  }

  const result: ( React.JSX.Element | string)[] = [];
  let pos = 0;
  for (const t of filtered) {
    if (t.start > pos) result.push(line.slice(pos, t.start));
    const color = tokenColor(t.type);
    result.push(<span key={`${t.start}-${t.type}`} style={{ color }}>{line.slice(t.start, t.end)}</span>);
    pos = t.end;
  }
  if (pos < line.length) result.push(line.slice(pos));
  if (result.length === 0) result.push(line);
  return result;
}

function tokenColor(type: string): string {
  switch (type) {
    case 'attr-name': return '#67e8f9'; // cyan
    case 'string': return '#86efac';     // green
    case 'number': return '#fcd34d';     // amber
    case 'boolean': return '#c084fc';    // purple
    case 'comment': return '#94a3b8';    // gray
    default: return '#e2e8f0';
  }
}
