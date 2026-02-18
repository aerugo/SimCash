# Admin Collection Management — Development Plan

**Status**: In Progress
**Date**: 2026-02-18
**Est. Time**: 2-3 hours

## Goal
Allow admins to tag scenarios into collections and create new collection tags via the admin dashboard.

## Current State
- Collections are hardcoded in `web/backend/app/collections.py` (5 collections, each with a fixed list of scenario IDs)
- Admin dashboard has a Library Curation tab that toggles visibility (show/archive) but cannot edit collection membership
- Collection data stored in Firestore `library_settings` collection with local fallback

## Changes

### Backend (`web/backend/app/collections.py`)
1. Add `POST /api/admin/collections` — create a new collection (name, icon, description)
2. Add `PUT /api/admin/collections/{id}/scenarios` — set scenario IDs for a collection
3. Add `DELETE /api/admin/collections/{id}` — delete a custom collection
4. Store custom collections in Firestore `library_settings/collections` document
5. Merge hardcoded + custom collections at load time (custom overrides hardcoded)

### Frontend (`web/frontend/src/views/AdminDashboard.tsx`)
1. In the Library Curation tab, show collections with their member scenarios
2. Add "Edit" button per collection → modal/inline editor to add/remove scenarios
3. Add "New Collection" button → form for name, icon, description
4. Drag-and-drop or checkbox-based scenario assignment

### Tests
- `test_collections.py`: test CRUD endpoints, Firestore persistence, merge logic

## Success Criteria
- [ ] Admin can create a new collection with name/icon/description
- [ ] Admin can add/remove scenarios from any collection
- [ ] Changes persist in Firestore
- [ ] Frontend reflects changes immediately
- [ ] Existing hardcoded collections still work as defaults
