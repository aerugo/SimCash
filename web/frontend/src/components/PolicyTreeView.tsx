import React, { useMemo } from 'react';

// ---- Types for policy tree nodes ----

interface PolicyConditionNode {
  type: 'condition';
  node_id: string;
  description?: string;
  condition: Record<string, unknown>;
  on_true: PolicyTreeNode;
  on_false: PolicyTreeNode;
}

interface PolicyActionNode {
  type: 'action';
  node_id: string;
  action: string;
  description?: string;
  parameters?: Record<string, unknown>;
}

type PolicyTreeNode = PolicyConditionNode | PolicyActionNode;

// ---- Layout types ----

interface LayoutNode {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  sublabel?: string;
  type: 'condition' | 'action';
  action?: string;
  children: { node: LayoutNode; label: string }[];
}

// ---- Helpers ----

const ACTION_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  Release:           { bg: '#065f46', border: '#10b981', text: '#6ee7b7' },
  ReleaseWithCredit: { bg: '#064e3b', border: '#059669', text: '#a7f3d0' },
  Hold:              { bg: '#78350f', border: '#f59e0b', text: '#fde68a' },
  HoldCollateral:    { bg: '#78350f', border: '#d97706', text: '#fcd34d' },
  Split:             { bg: '#164e63', border: '#06b6d4', text: '#a5f3fc' },
  PostCollateral:    { bg: '#1e3a5f', border: '#3b82f6', text: '#93c5fd' },
  WithdrawCollateral:{ bg: '#4c1d95', border: '#8b5cf6', text: '#c4b5fd' },
  NoAction:          { bg: '#334155', border: '#64748b', text: '#94a3b8' },
};

const CONDITION_STYLE = { bg: '#1e293b', border: '#475569', text: '#e2e8f0' };

const NODE_W = 160;
const NODE_H = 52;
const H_GAP = 24;
const V_GAP = 60;

function formatCondition(cond: Record<string, unknown>): string {
  if (!cond) return '?';
  const op = cond.op as string;
  if (op === 'and' || op === 'or') {
    return op.toUpperCase();
  }
  const left = formatOperand(cond.left as Record<string, unknown>);
  const right = formatOperand(cond.right as Record<string, unknown>);
  return `${left} ${op} ${right}`;
}

function formatOperand(o: unknown): string {
  if (!o || typeof o !== 'object') return String(o ?? '?');
  const obj = o as Record<string, unknown>;
  if ('field' in obj) return String(obj.field);
  if ('param' in obj) return String(obj.param);
  if ('value' in obj) return String(obj.value);
  if ('compute' in obj) return 'expr';
  return '?';
}

// ---- Tree width calculation ----

function treeWidth(node: PolicyTreeNode): number {
  if (node.type === 'action') return 1;
  return treeWidth(node.on_true) + treeWidth(node.on_false);
}

// ---- Layout calculation ----

function layoutTree(
  node: PolicyTreeNode,
  x: number,
  y: number,
): LayoutNode {
  if (node.type === 'action') {
    return {
      id: node.node_id,
      x, y,
      width: NODE_W,
      height: NODE_H,
      label: node.action,
      type: 'action',
      action: node.action,
      children: [],
    };
  }

  const condLabel = node.description
    ? (node.description.length > 40 ? node.description.slice(0, 37) + '…' : node.description)
    : formatCondition(node.condition);

  const leftW = treeWidth(node.on_true);
  const rightW = treeWidth(node.on_false);
  const totalW = leftW + rightW;

  const spanPx = totalW * (NODE_W + H_GAP) - H_GAP;
  const leftSpanPx = leftW * (NODE_W + H_GAP) - H_GAP;

  const leftCenterX = x - spanPx / 2 + leftSpanPx / 2;
  const rightCenterX = x + spanPx / 2 - (rightW * (NODE_W + H_GAP) - H_GAP) / 2;

  const childY = y + NODE_H + V_GAP;

  const trueLayout = layoutTree(node.on_true, leftCenterX, childY);
  const falseLayout = layoutTree(node.on_false, rightCenterX, childY);

  return {
    id: node.node_id,
    x, y,
    width: NODE_W,
    height: NODE_H,
    label: condLabel,
    sublabel: formatCondition(node.condition),
    type: 'condition',
    children: [
      { node: trueLayout, label: 'Yes' },
      { node: falseLayout, label: 'No' },
    ],
  };
}

// ---- Bounds ----

function getBounds(node: LayoutNode): { minX: number; maxX: number; minY: number; maxY: number } {
  let minX = node.x - node.width / 2;
  let maxX = node.x + node.width / 2;
  let minY = node.y;
  let maxY = node.y + node.height;
  for (const c of node.children) {
    const cb = getBounds(c.node);
    minX = Math.min(minX, cb.minX);
    maxX = Math.max(maxX, cb.maxX);
    minY = Math.min(minY, cb.minY);
    maxY = Math.max(maxY, cb.maxY);
  }
  return { minX, maxX, minY, maxY };
}

// ---- SVG rendering ----

function renderNode(node: LayoutNode, elements: React.JSX.Element[]) {
  const isAction = node.type === 'action';
  const colors = isAction
    ? (ACTION_COLORS[node.action || ''] || ACTION_COLORS.NoAction)
    : CONDITION_STYLE;

  const rx = isAction ? 6 : 12;

  const tooltipText = node.sublabel
    ? `${node.label}\n${node.sublabel}`
    : node.label;

  elements.push(
    <g key={node.id} style={{ cursor: 'default' }}>
      <title>{tooltipText}</title>
      {/* Shadow */}
      <rect
        x={node.x - node.width / 2 + 2}
        y={node.y + 2}
        width={node.width}
        height={node.height}
        rx={rx}
        fill="rgba(0,0,0,0.3)"
      />
      {/* Box */}
      <rect
        x={node.x - node.width / 2}
        y={node.y}
        width={node.width}
        height={node.height}
        rx={rx}
        fill={colors.bg}
        stroke={colors.border}
        strokeWidth={1.5}
      />
      {/* Label */}
      <text
        x={node.x}
        y={node.y + (node.sublabel && !isAction ? node.height / 2 - 6 : node.height / 2 + 1)}
        textAnchor="middle"
        dominantBaseline="central"
        fill={colors.text}
        fontSize={isAction ? 12 : 10}
        fontWeight={isAction ? 600 : 400}
        fontFamily="ui-monospace, monospace"
      >
        {truncate(node.label, isAction ? 20 : 24)}
      </text>
      {/* Sublabel for conditions */}
      {!isAction && node.sublabel && (
        <text
          x={node.x}
          y={node.y + node.height / 2 + 8}
          textAnchor="middle"
          dominantBaseline="central"
          fill="#94a3b8"
          fontSize={8}
          fontFamily="ui-monospace, monospace"
        >
          {truncate(node.sublabel, 28)}
        </text>
      )}
    </g>
  );

  for (const child of node.children) {
    const startX = node.x;
    const startY = node.y + node.height;
    const endX = child.node.x;
    const endY = child.node.y;
    const midY = (startY + endY) / 2;

    elements.push(
      <g key={`edge-${node.id}-${child.node.id}`}>
        <path
          d={`M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}`}
          fill="none"
          stroke="#475569"
          strokeWidth={1.5}
        />
        {/* Arrow head */}
        <polygon
          points={`${endX},${endY} ${endX - 4},${endY - 6} ${endX + 4},${endY - 6}`}
          fill="#475569"
        />
        {/* Branch label */}
        <text
          x={(startX + endX) / 2 + (child.label === 'Yes' ? -10 : 10)}
          y={midY - 2}
          textAnchor="middle"
          fill={child.label === 'Yes' ? '#6ee7b7' : '#fca5a5'}
          fontSize={9}
          fontWeight={600}
          fontFamily="sans-serif"
        >
          {child.label}
        </text>
      </g>
    );

    renderNode(child.node, elements);
  }
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + '…' : s;
}

// ---- Component ----

interface PolicyTreeViewProps {
  tree: Record<string, unknown>;
  title?: string;
  className?: string;
}

export function PolicyTreeView({ tree, title, className = '' }: PolicyTreeViewProps) {
  const { svg, viewBox } = useMemo(() => {
    if (!tree || !tree.type) return { svg: null, viewBox: '0 0 200 100' };

    const node = tree as unknown as PolicyTreeNode;
    const w = treeWidth(node);
    const centerX = (w * (NODE_W + H_GAP)) / 2;
    const root = layoutTree(node, centerX, 20);
    const bounds = getBounds(root);

    const pad = 20;
    const vb = `${bounds.minX - pad} ${bounds.minY - pad} ${bounds.maxX - bounds.minX + pad * 2} ${bounds.maxY - bounds.minY + pad * 2 + 10}`;

    const elements: React.JSX.Element[] = [];
    renderNode(root, elements);

    return { svg: elements, viewBox: vb };
  }, [tree]);

  if (!svg) {
    return (
      <div className={`flex items-center justify-center py-8 text-slate-500 text-sm ${className}`}>
        No tree data
      </div>
    );
  }

  return (
    <div className={className}>
      {title && (
        <h3 className="text-sm font-semibold text-slate-400 mb-2">{title}</h3>
      )}
      <div className="bg-slate-900/50 rounded-lg border border-slate-700/50 overflow-auto">
        <svg
          viewBox={viewBox}
          className="w-full"
          style={{ minHeight: 200, maxHeight: 600 }}
          preserveAspectRatio="xMidYMin meet"
        >
          {svg}
        </svg>
      </div>
    </div>
  );
}
