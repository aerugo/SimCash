# Password Auth — Feature Plan

**Status**: Draft  
**Date**: 2026-02-21  
**Estimated effort**: ~4-6 hours

## Goal

Replace Google/magic-link as the default login with email+password. Admins generate passphrase-based initial passwords for new users. Users can change their own password after first login.

## Current State

- Firebase Auth with Google sign-in (popup/redirect) and magic link (email link)
- Firestore `allowed_users` collection for access control (invite-based)
- Admin dashboard at `/admin` with invite/revoke
- `LoginPage.tsx`: Google button + magic link email input
- Backend `auth.py`: verifies Firebase ID tokens (works with any Firebase Auth provider)

## Key Insight

**Firebase Auth already supports email+password** — `createUserWithEmailAndPassword`, `signInWithEmailAndPassword`. The backend token verification (`firebase_admin.auth.verify_id_token`) works identically regardless of sign-in method. So the backend needs minimal changes.

## Design

### Admin Flow: Generate Passphrase for New User

1. Admin goes to `/admin`, enters email to invite
2. Backend creates a Firebase Auth user with a generated passphrase (e.g., `correct-horse-battery-staple` style)
3. Backend also adds user to `allowed_users` (existing flow)
4. Backend returns the passphrase to the admin
5. Admin copies it and sends it to the user via email/chat

**Why server-side user creation?** Firebase Admin SDK can create users with arbitrary passwords and set `emailVerified: true`, bypassing email verification. This keeps the flow clean — admin creates account, user just logs in.

### User Flow: Login

1. User enters email + passphrase on login page
2. Firebase client SDK `signInWithEmailAndPassword(email, password)`
3. Normal Firebase Auth flow — gets ID token, backend verifies it, checks `allowed_users`
4. On first login, show a "Change your password" prompt (optional but recommended)

### User Flow: Change Password

1. User clicks "Change Password" (in header menu or settings)
2. Modal: current password + new password + confirm
3. Firebase client SDK: `reauthenticateWithCredential(credential)` then `updatePassword(newPassword)`
4. No backend involvement needed — Firebase handles it

### Passphrase Generation

Use a wordlist-based approach (BIP39-style or EFF diceware):
- 4 words, hyphen-separated: `marble-sunset-falcon-bridge`
- ~44 bits of entropy (sufficient for initial password that gets changed)
- Easy to read aloud / type from email

## Changes

### Backend

| File | Change |
|------|--------|
| `web/backend/app/admin.py` | New `create_user_with_passphrase(email)` method using Firebase Admin SDK `auth.create_user(email=email, password=passphrase)` + `auth.update_user(uid, email_verified=True)`. Returns passphrase. |
| `web/backend/app/main.py` | New endpoint `POST /api/admin/create-user` — calls `create_user_with_passphrase`, also does `invite_user`. Returns `{ email, passphrase }`. |
| `web/backend/app/wordlist.py` | Passphrase generator — 2048-word list, pick 4 at random with `secrets.choice`. |

### Frontend

| File | Change |
|------|--------|
| `firebase.ts` | Add `signInWithPassword(email, password)`, `changePassword(currentPassword, newPassword)` using Firebase client SDK. |
| `LoginPage.tsx` | Replace magic link section with email+password form as the **primary** login. Keep Google as secondary "or sign in with Google". |
| `AuthContext.tsx` | No changes needed — `onAuthStateChanged` works the same regardless of sign-in method. |
| `AdminDashboard.tsx` | Replace "Invite" button with "Create User" — shows generated passphrase in a copyable box after creation. |
| `Layout.tsx` or new `ChangePasswordModal.tsx` | "Change Password" option in user menu dropdown. |

### What stays the same

- Backend token verification — unchanged (Firebase ID tokens are provider-agnostic)
- `allowed_users` Firestore collection — still used for access control
- Dev token auth — unchanged
- WebSocket auth — unchanged

## Login Page Layout (new)

```
💰 SimCash
Interactive Payment Simulator

[Email                    ]
[Password                 ]
[       Sign In           ]

[Forgot password?]

─── or ───

[G] Sign in with Google

Access restricted to authorized users
```

## Admin Dashboard: Create User

```
Create New User
[Email                    ]
[    Generate Credentials  ]

┌──────────────────────────────┐
│ ✅ User created!             │
│ Email: alice@bank.com        │
│ Password: marble-sunset-     │
│           falcon-bridge      │
│ [📋 Copy]                   │
│                              │
│ Send these credentials to    │
│ the user. They can change    │
│ their password after login.  │
└──────────────────────────────┘
```

## Password Change Modal

```
Change Password
[Current password         ]
[New password             ]
[Confirm new password     ]
[       Update            ]
```

## Migration

- **Existing Google users continue to work** — Firebase Auth supports multiple providers per email. Users who already signed in with Google can keep doing so.
- **No data migration needed** — `allowed_users` collection stays the same.
- **Magic link can be removed** — or kept as fallback. Recommend removing to simplify.

## Security Considerations

- Passphrases generated with `secrets.choice` (CSPRNG)
- Admin endpoint requires admin auth (existing `require_admin` dependency)
- Passphrase shown once, never stored in plaintext (Firebase hashes it)
- Firebase handles rate limiting on login attempts
- `updatePassword` requires recent authentication (Firebase enforces this)

## Testing

- Unit test: passphrase generation (word count, format, uniqueness)
- Unit test: `create_user_with_passphrase` (mock Firebase Admin SDK)
- Manual: create user via admin → login with passphrase → change password → login with new password
- Manual: existing Google users still work

## Not in scope

- Password complexity requirements (passphrase is strong enough, user-chosen passwords are their problem)
- Account lockout (Firebase handles this natively)
- "Forgot password" flow via email reset (can add later with `sendPasswordResetEmail`)
- Two-factor auth
