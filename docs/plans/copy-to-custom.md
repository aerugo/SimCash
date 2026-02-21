# Copy to Custom — Feature Plan

**Status**: Draft  
**Date**: 2026-02-22  
**Estimated effort**: ~2-3 hours

## Goal

Add a "Copy" button to built-in library scenarios and policies that creates an editable custom copy in the user's "My Scenarios" / "My Policies" tab.

## User Flow

### Scenarios
1. User opens a built-in scenario in the Library detail panel
2. Clicks **📋 Copy to My Scenarios**
3. Frontend fetches the full scenario detail (YAML + metadata) — already available via `getScenarioLibraryDetail(id)`
4. Calls `saveCustomScenario({ name: "Copy of {original}", description: original.description, yaml_string: original.yaml_config })`
5. On success: toast/banner "Saved! Opening editor…", navigate to `/create?edit={newId}` (existing edit mode)
6. User lands in the Scenario Editor with the copy loaded, ready to modify

### Policies
1. User opens a built-in policy in the Library detail panel
2. Clicks **📋 Copy to My Policies**
3. Frontend fetches full policy detail — already available via `getPolicyLibraryDetail(id)`
4. Calls `saveCustomPolicyApi({ name: "Copy of {original}", description: original.description, json_string: JSON.stringify(original.policy_json) })`
5. On success: navigate to `/create?editPolicy={newId}`
6. User lands in the Policy Editor with the copy loaded

## Changes

### Frontend only — no backend changes needed

Everything required already exists:
- `getScenarioLibraryDetail(id)` returns `yaml_config` (the full YAML string)
- `getPolicyLibraryDetail(id)` returns `policy_json` (the full JSON object)
- `saveCustomScenario()` / `saveCustomPolicyApi()` create new custom items
- Edit mode in editors already works via `?edit={id}` / `?editPolicy={id}` query params

### Files to modify

| File | Change |
|------|--------|
| `ScenarioLibraryView.tsx` | Add "Copy to My Scenarios" button in the detail panel (where Launch button is). Disable for guests (`isGuest`). |
| `PolicyLibraryView.tsx` | Add "Copy to My Policies" button in the detail panel. Need `useAuthInfo()` import for guest check. |

### Button placement

**Scenario detail panel**: Next to the existing "🚀 Launch" button, add a secondary "📋 Copy" button. Same row, outlined/ghost style to distinguish from primary action.

**Policy detail panel**: Next to "Select Policy" (if `onSelectPolicy` provided) or standalone. Same pattern.

### Edge cases

- **Guest users**: Button hidden or disabled with tooltip "Sign in to save copies"
- **Name collision**: Backend handles — Firestore generates unique IDs, duplicate names are fine
- **Copy of a copy**: Works naturally — user can copy their own custom items too (but that's already possible via edit+save-as-new, so low priority)
- **Large YAML/JSON**: No issue — same size limits as manual save

## Implementation Sketch

```tsx
// In ScenarioLibraryView.tsx, inside the detail panel:
const handleCopyScenario = async () => {
  if (!selectedScenario) return;
  setCopying(true);
  try {
    const saved = await saveCustomScenario({
      name: `Copy of ${selectedScenario.name}`,
      description: selectedScenario.description,
      yaml_string: selectedScenario.yaml_config,
    });
    navigate(`/create?edit=${saved.id}`);
  } catch (e) {
    setError((e as Error).message);
  } finally {
    setCopying(false);
  }
};

// Button (next to Launch):
{!isGuest && (
  <button onClick={handleCopyScenario} disabled={copying}
    className="px-4 py-2 rounded-lg border border-sky-500/50 text-sky-400 hover:bg-sky-500/10 text-sm">
    {copying ? '📋 Copying…' : '📋 Copy & Edit'}
  </button>
)}
```

Same pattern for policies.

## Testing

- Manual: Copy a built-in scenario → verify it appears in My Scenarios → edit YAML → save
- Manual: Copy a built-in policy → verify it appears in My Policies → edit JSON → save
- Verify guest users don't see the button
- Verify the copied content is identical to the original

## Not in scope

- "Fork" semantics (tracking lineage/parent)
- Bulk copy
- Copy between users
