# Implementation Plans

This directory contains detailed implementation plans for enhancing the Payment Simulator.

## Active Plans

### [T2-Realistic LSM Implementation](t2-realistic-lsm-implementation.md)
**Status**: Planning complete, ready for implementation
**Priority**: High
**Estimated Effort**: 5-6 days

Brings our Liquidity-Saving Mechanism (LSM) into full compliance with T2 RTGS specifications. Key enhancement: Support multilateral cycle settlement with unequal payment values, where each participant covers their net position rather than settling only the minimum amount.

**Key Insight from T2 Research**: T2's "partial netting" refers to handling **unequal payment values in cycles**, not splitting individual transactions. Each payment settles in full or not at all.

---

## Archived Plans

### [LSM Splitting Investigation](lsm-splitting-investigation-plan.md)
**Status**: Superseded by T2-realistic implementation
**Reason**: Research revealed T2 doesn't split transactions at RTGS level; splitting only occurs at bank's Queue 1 decision point

### [Realistic Dropped Transactions](realistic-dropped-transactions.md)
**Status**: Complete
**Implementation**: Overdue transaction handling integrated

---

## Plan Index

| Plan | Status | Priority | Effort | Phase |
|------|--------|----------|--------|-------|
| [T2-Realistic LSM](t2-realistic-lsm-implementation.md) | 📋 Planned | High | 5-6 days | 3.5 |
| [LSM Splitting Investigation](lsm-splitting-investigation-plan.md) | ❌ Superseded | - | - | - |
| [Realistic Dropped Transactions](realistic-dropped-transactions.md) | ✅ Complete | - | - | - |

---

*Last Updated: 2025-11-05*
