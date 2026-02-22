import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import type { PolicyJson, BootstrapResult } from '../types';
import { PolicyTreeView } from './PolicyTreeView';

export interface PolicyViewerModalProps {
  policy: PolicyJson;
  onClose: () => void;
  title?: string;
  rejected?: boolean;
  rejectionReason?: string;
  bootstrap?: BootstrapResult;
}

export function PolicyViewerModal({ policy, onClose, title, rejected, rejectionReason, bootstrap }: PolicyViewerModalProps) {
  const [viewMode, setViewMode] = useState<'tree' | 'json'>('tree');
  const [treeTab, setTreeTab] = useState<'payment' | 'bank'>('payment');

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
  }, [onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const params = policy.parameters || {};
  const paymentTree = policy.payment_tree;
  const bankTree = policy.bank_tree;

  return createPortal(
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-color)',
          borderRadius: '12px', maxWidth: '800px', width: '100%',
          maxHeight: '85vh', overflow: 'auto', padding: '1.5rem',
          color: 'var(--text-primary)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>
              {title || 'Policy Viewer'}
            </h3>
            {rejected && (
              <span style={{
                background: 'var(--color-danger, #ef4444)', color: '#fff',
                fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px',
                borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.05em',
              }}>
                Rejected
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', color: 'var(--text-muted)',
              fontSize: '1.25rem', cursor: 'pointer', padding: '4px',
            }}
          >
            ✕
          </button>
        </div>

        {/* Rejection info */}
        {rejected && rejectionReason && (
          <div style={{
            background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: '8px', padding: '0.75rem', marginBottom: '1rem',
            fontSize: '0.8rem', color: 'var(--color-danger, #ef4444)',
          }}>
            <strong>Rejection reason:</strong> {rejectionReason}
          </div>
        )}

        {/* Bootstrap stats */}
        {rejected && bootstrap && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: '1rem',
            fontSize: '0.75rem', fontFamily: 'monospace', color: 'var(--text-muted)',
            marginBottom: '1rem', padding: '0.5rem 0.75rem',
            background: 'var(--bg-inset)', borderRadius: '6px',
          }}>
            <span>Δ {bootstrap.delta_sum.toLocaleString()}</span>
            <span>CV {bootstrap.cv.toFixed(2)}</span>
            <span>CI [{bootstrap.ci_lower.toLocaleString()}, {bootstrap.ci_upper.toLocaleString()}]</span>
            <span>n={bootstrap.num_samples}</span>
          </div>
        )}

        {/* Parameters */}
        {Object.keys(params).length > 0 && (
          <div style={{
            marginBottom: '1rem', padding: '0.75rem',
            background: 'var(--bg-inset)', borderRadius: '8px',
          }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
              Parameters
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', fontSize: '0.8rem', fontFamily: 'monospace' }}>
              {Object.entries(params).map(([k, v]) => (
                <span key={k} style={{ color: 'var(--text-primary)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{k}:</span>{' '}
                  {typeof v === 'number' ? v.toFixed(4) : String(v)}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Toggle: Tree / JSON */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
          {(['tree', 'json'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              style={{
                padding: '4px 12px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 500,
                border: `1px solid ${viewMode === mode ? 'var(--btn-primary-bg)' : 'var(--border-color)'}`,
                background: viewMode === mode ? 'var(--btn-primary-bg)' : 'transparent',
                color: viewMode === mode ? '#fff' : 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              {mode === 'tree' ? '🌳 Tree' : '{ } JSON'}
            </button>
          ))}

          {viewMode === 'tree' && (
            <div style={{ display: 'flex', gap: '0.25rem', marginLeft: '0.5rem' }}>
              {(['payment', 'bank'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setTreeTab(tab)}
                  style={{
                    padding: '3px 10px', borderRadius: '4px', fontSize: '0.7rem',
                    border: `1px solid ${treeTab === tab ? 'var(--text-secondary)' : 'var(--border-color)'}`,
                    background: treeTab === tab ? 'var(--bg-surface)' : 'transparent',
                    color: treeTab === tab ? 'var(--text-primary)' : 'var(--text-muted)',
                    cursor: 'pointer',
                  }}
                >
                  {tab === 'payment' ? 'Payment Tree' : 'Bank Tree'}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Content */}
        {viewMode === 'tree' ? (
          <div>
            {treeTab === 'payment' && paymentTree ? (
              <PolicyTreeView tree={paymentTree} title="Payment Tree" />
            ) : treeTab === 'payment' ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '1rem', textAlign: 'center' }}>No payment tree</div>
            ) : null}
            {treeTab === 'bank' && bankTree ? (
              <PolicyTreeView tree={bankTree} title="Bank Tree" />
            ) : treeTab === 'bank' ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '1rem', textAlign: 'center' }}>No bank tree</div>
            ) : null}
          </div>
        ) : (
          <pre style={{
            background: 'var(--bg-surface)', border: '1px solid var(--border-color)',
            borderRadius: '8px', padding: '1rem', fontSize: '0.75rem',
            overflow: 'auto', maxHeight: '400px', fontFamily: 'monospace',
            color: 'var(--text-secondary)',
          }}>
            {JSON.stringify(policy, null, 2)}
          </pre>
        )}
      </div>
    </div>,
    document.body
  );
}
