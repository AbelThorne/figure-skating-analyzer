# User Password Change — Design Spec

## Overview

Add the ability for any authenticated user to change their own password, and for admins to force a password change on next login when creating a user account.

## Backend Changes

### User Model

Add field to `backend/app/models/user.py`:
- `must_change_password: bool = False` — column default `False`

Add migration entry in `backend/app/database.py` `_MIGRATIONS`:
- `("users", "must_change_password", "BOOLEAN DEFAULT 0")`

### New Endpoint: `POST /api/auth/change-password`

Accessible to any authenticated user (no admin requirement).

**Input:**
```json
{ "current_password": "string", "new_password": "string" }
```

**Validation:**
- `current_password` verified against stored hash (401 if wrong)
- `new_password` must be >= 8 characters (400 if too short)
- User must have a `password_hash` set (400 if OAuth-only account)

**On success:**
- Hash and store `new_password`
- Set `must_change_password = False`
- Increment `token_version` (invalidates old refresh tokens)
- Return new `access_token` + set new `refresh_token` cookie
- Status 200

### Modified: Login Response

`POST /api/auth/login` and `POST /api/auth/refresh` — add `must_change_password` to the `user` object in the response:

```json
{
  "access_token": "...",
  "user": {
    "id": "...",
    "email": "...",
    "display_name": "...",
    "role": "admin",
    "must_change_password": true,
    "has_password": true
  }
}
```

### Modified: User Creation

`POST /api/users/` — accept optional `must_change_password: bool` in the request body. Only meaningful when `password` is also provided. Defaults to `False`.

## Frontend Changes

### Types

Update `AuthUser` in `frontend/src/api/client.ts`:
```typescript
export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "reader";
  must_change_password: boolean;
  has_password: boolean;
}
```

Add API function:
```typescript
api.auth.changePassword: (current_password: string, new_password: string) => Promise<LoginResponse>
```

### Profile Page — `/profil`

New page `frontend/src/pages/ProfilePage.tsx`, accessible to all authenticated users.

**Content:**
- Heading: "Mon compte"
- If user is OAuth-only (no password_hash): show message "Vous utilisez Google pour vous connecter. La modification du mot de passe n'est pas disponible." and no form.
- Otherwise: form with three fields — Mot de passe actuel, Nouveau mot de passe, Confirmer le nouveau mot de passe
- Submit button: "Changer le mot de passe"
- Client-side validation: new password fields must match, min 8 characters
- On success: message "Mot de passe modifie avec succes", call `setAccessToken()` with the returned token and update user in AuthContext
- On error (wrong current password): inline error message

### Navigation

In the sidebar (`App.tsx`), the user name/email at the bottom becomes a link to `/profil`. No new entry in the main nav list. Add `<Route path="/profil" element={<ProfilePage />} />` to the Routes in `AuthenticatedLayout`. Add `/profil` → "Mon compte" to `getPageTitle()`.

### Forced Password Change Modal

**Trigger:** In `AuthenticatedLayout`, if `user.must_change_password === true` and not dismissed this session, show a modal.

**Modal content:** Same form as the profile page (current password, new password, confirm). If OAuth-only user, show info message and close button only.

**Behavior:**
- Dismissable — user can close the modal without changing
- Dismissal state stored in `sessionStorage` (key: `password_change_dismissed`) — modal won't reappear in the same session
- If dismissed, an orange warning dot (`bg-orange-500 w-2 h-2 rounded-full`) appears next to the user name in the sidebar
- The dot disappears once the password is changed (either via modal or profile page) — i.e. when `user.must_change_password` becomes `false`

### Admin: User Creation Checkbox

In `SettingsPage.tsx`, in the "create user" form:
- Add a checkbox "Forcer le changement au prochain login" below the password field
- Reactively visible only when the password field has a value
- Sends `must_change_password: true` in the creation payload

## UI Text (French)

| Key | Text |
|-----|------|
| Page title | Mon compte |
| Current password label | Mot de passe actuel |
| New password label | Nouveau mot de passe |
| Confirm password label | Confirmer le nouveau mot de passe |
| Submit button | Changer le mot de passe |
| Success message | Mot de passe modifie avec succes |
| Wrong password error | Mot de passe actuel incorrect |
| Too short error | Le mot de passe doit contenir au moins 8 caracteres |
| Mismatch error | Les mots de passe ne correspondent pas |
| Modal title | Changement de mot de passe requis |
| Modal subtitle | Un administrateur a demande que vous changiez votre mot de passe. |
| Admin checkbox | Forcer le changement au prochain login |

## Files Summary

| Action | File |
|--------|------|
| Modify | `backend/app/models/user.py` |
| Modify | `backend/app/database.py` |
| Modify | `backend/app/routes/auth.py` |
| Modify | `backend/app/routes/users.py` |
| Create | `backend/tests/test_change_password.py` |
| Modify | `frontend/src/api/client.ts` |
| Create | `frontend/src/pages/ProfilePage.tsx` |
| Create | `frontend/src/components/ForcePasswordModal.tsx` |
| Modify | `frontend/src/App.tsx` |
| Modify | `frontend/src/pages/SettingsPage.tsx` |
| Modify | `frontend/src/auth/AuthContext.tsx` |
