# Phase 5: Admin System, Invites, Magic Links

## Requirements
1. Any `@sensestack.xyz` Google user can sign in directly
2. Admin users (initially `hugi@sensestack.xyz`) can invite arbitrary emails
3. Invited users without Google accounts sign in via magic link (email link sign-in)
4. Admin dashboard: list users, invite new users, revoke access

## Firebase Setup

### Enable Email Link Sign-In
Firebase Console → Authentication → Sign-in method → Email/Password → Enable **Email link (passwordless sign-in)**

### Dynamic Links / Hosting
Magic links need a URL to redirect to. Options:
- Firebase Hosting (just for the auth redirect) — simplest
- Or handle the link in the Cloud Run app directly via `finishSignInWithEmailLink()`

## Data Model

### Firestore Collections

```
/admins/{email}
  - email: string
  - added_by: string
  - added_at: timestamp

/allowed_users/{email}
  - email: string
  - invited_by: string (admin email)
  - invited_at: timestamp
  - status: "invited" | "active"
  - sign_in_method: "google" | "email_link"
  - last_login: timestamp | null

/invitations/{token}
  - email: string
  - created_by: string
  - created_at: timestamp
  - expires_at: timestamp
  - used: boolean
```

### Access Rules
1. `@sensestack.xyz` emails → always allowed (hardcoded domain check)
2. Email in `/allowed_users/` → allowed
3. Everyone else → rejected after Firebase auth, shown "Access denied, contact admin"

## Backend Changes

### New: `web/backend/app/admin.py`
```python
# Firestore-backed user management
class UserManager:
    def __init__(self):
        self.db = firestore.client()
    
    def is_allowed(self, email: str) -> bool:
        """Check if email is allowed (domain or invited)."""
        if email.endswith("@sensestack.xyz"):
            return True
        doc = self.db.collection("allowed_users").document(email).get()
        return doc.exists
    
    def is_admin(self, email: str) -> bool:
        doc = self.db.collection("admins").document(email).get()
        return doc.exists
    
    def invite_user(self, email: str, invited_by: str) -> None:
        self.db.collection("allowed_users").document(email).set({...})
    
    def list_users(self) -> list[dict]:
        return [doc.to_dict() for doc in self.db.collection("allowed_users").stream()]
    
    def revoke_user(self, email: str) -> None:
        self.db.collection("allowed_users").document(email).delete()
```

### Modified: `web/backend/app/auth.py`
- After verifying Firebase token, check `user_manager.is_allowed(email)`
- If not allowed → 403 with message
- Add admin check dependency: `get_admin_user()`

### New endpoints
```
GET  /api/admin/users          — list all users (admin only)
POST /api/admin/invite         — invite user by email (admin only)  
DELETE /api/admin/users/{email} — revoke user (admin only)
GET  /api/admin/me             — check if current user is admin
```

## Frontend Changes

### Modified: `LoginPage.tsx`
- Google sign-in button (existing)
- "Sign in with email" section:
  - Email input + "Send magic link" button
  - After sending: "Check your email for a sign-in link"
- Handle `isSignInWithEmailLink()` on page load (complete magic link flow)

### New: `AdminDashboard.tsx`
- Only visible to admins
- User list table: email, status, sign-in method, last login, invite date
- "Invite user" form: email input + invite button
- Revoke button per user
- Simple, dark-themed, consistent with existing UI

### Modified: `App.tsx`
- After auth: check if user is allowed → if not, show "Access denied" page
- Add admin nav item if user is admin

## Implementation Order
1. Enable Email Link sign-in in Firebase Console (manual)
2. Backend: Firestore init, UserManager, admin endpoints, access check in auth
3. Frontend: magic link sign-in flow in LoginPage
4. Frontend: AdminDashboard component
5. Seed Firestore: add `hugi@sensestack.xyz` to `/admins/`
6. Test: Google sign-in (sensestack.xyz), magic link invite flow, admin dashboard
7. Rebuild + redeploy Docker image

## Dependencies
- `google-cloud-firestore` (already installed via firebase-admin)
- Firestore needs to be enabled in Firebase Console
- Firebase Email Link sign-in needs to be enabled
