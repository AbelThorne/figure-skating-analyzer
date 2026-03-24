# User Password Change Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any user change their own password, and let admins force a password change on next login.

**Architecture:** Add `must_change_password` column to User model. New `POST /api/auth/change-password` endpoint. Frontend gets a profile page at `/profil` and a dismissable modal that appears when `must_change_password` is true. Admin user creation form gets a checkbox.

**Tech Stack:** Python/Litestar + SQLAlchemy (backend), React/TypeScript + Tailwind CSS (frontend), pytest async (tests)

**Spec:** `docs/superpowers/specs/2026-03-24-user-password-change-design.md`

---

### Task 1: User Model — Add `must_change_password` Field

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/database.py`

- [ ] **Step 1: Add the column to the User model**

In `backend/app/models/user.py`, add after line 30 (`token_version`):

```python
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 2: Add the migration entry**

In `backend/app/database.py`, add to the `_MIGRATIONS` list (line 40-48), inside the list before the closing `]`:

```python
        ("users", "must_change_password", "BOOLEAN DEFAULT 0"),
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `PATH="/opt/homebrew/bin:$PATH" uv run --project backend pytest backend/tests/ -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/user.py backend/app/database.py
git commit -m "feat: add must_change_password field to User model"
```

---

### Task 2: Backend — Change Password Endpoint

**Files:**
- Modify: `backend/app/routes/auth.py`
- Create: `backend/tests/test_change_password.py`

- [ ] **Step 1: Write the tests**

Create `backend/tests/test_change_password.py`:

```python
"""Tests for password change endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, admin_user, admin_token: str, db_session: AsyncSession):
    user, old_password = admin_user
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": old_password, "new_password": "newpass1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == user.email

    # Verify can login with new password
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "newpass1234"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpass1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_too_short(client: AsyncClient, admin_user, admin_token: str):
    _, old_password = admin_user
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": old_password, "new_password": "short"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_password_clears_must_change_flag(client: AsyncClient, admin_user, admin_token: str, db_session: AsyncSession):
    user, old_password = admin_user
    # Set the flag
    user.must_change_password = True
    await db_session.commit()

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": old_password, "new_password": "newpass1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["must_change_password"] is False

    # Verify in DB
    await db_session.refresh(user)
    assert user.must_change_password is False


@pytest.mark.asyncio
async def test_change_password_increments_token_version(client: AsyncClient, admin_user, admin_token: str, db_session: AsyncSession):
    user, old_password = admin_user
    old_version = user.token_version

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": old_password, "new_password": "newpass1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    await db_session.refresh(user)
    assert user.token_version == old_version + 1


@pytest.mark.asyncio
async def test_change_password_unauthenticated(client: AsyncClient):
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "old", "new_password": "newpass1234"},
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PATH="/opt/homebrew/bin:$PATH" uv run --project backend pytest backend/tests/test_change_password.py -v`
Expected: FAIL — 404 (route not found)

- [ ] **Step 3: Implement the endpoint**

In `backend/app/routes/auth.py`, update `_user_dict` (line 31-37) to include the new fields:

```python
def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "must_change_password": user.must_change_password,
        "has_password": user.password_hash is not None,
    }
```

Add the change-password handler before the `router = Router(...)` line (before line 252):

```python
@post("/change-password")
async def change_password(data: dict, request: Request, session: AsyncSession) -> Response:
    user_id = request.scope["state"].get("user_id")
    if not user_id:
        raise NotAuthorizedException("Not authenticated")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotAuthorizedException("User not found")

    if not user.password_hash:
        return Response(
            content={"detail": "OAuth-only account cannot change password"},
            status_code=400,
        )

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not verify_password(current_password, user.password_hash):
        return Response(
            content={"detail": "Current password is incorrect"},
            status_code=401,
        )

    if len(new_password) < 8:
        return Response(
            content={"detail": "Password must be at least 8 characters"},
            status_code=400,
        )

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.token_version += 1
    await session.commit()
    await session.refresh(user)

    access = create_access_token(user_id=user.id, role=user.role)
    refresh = create_refresh_token(user_id=user.id, token_version=user.token_version)

    response = Response(
        content={"access_token": access, "user": _user_dict(user)},
        status_code=200,
    )
    _set_refresh_cookie(response, refresh)
    return response
```

Update the router registration to include the new handler:

```python
router = Router(
    path="/api/auth",
    route_handlers=[login, refresh, logout, setup, google_login, change_password],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PATH="/opt/homebrew/bin:$PATH" uv run --project backend pytest backend/tests/test_change_password.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `PATH="/opt/homebrew/bin:$PATH" uv run --project backend pytest backend/tests/ -v --timeout=30`
Expected: All tests PASS. Note: existing auth tests (`test_auth.py`) now get `must_change_password` and `has_password` in the user response — these tests don't assert on those fields so they should still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/auth.py backend/tests/test_change_password.py
git commit -m "feat: add change-password endpoint with tests"
```

---

### Task 3: Backend — User Creation with `must_change_password`

**Files:**
- Modify: `backend/app/routes/users.py`
- Modify: `backend/tests/test_change_password.py`

- [ ] **Step 1: Write the test**

Add to `backend/tests/test_change_password.py`:

```python
@pytest.mark.asyncio
async def test_create_user_with_must_change_password(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/users/",
        json={
            "email": "newuser@test.com",
            "display_name": "New User",
            "role": "reader",
            "password": "temppass123",
            "must_change_password": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@test.com"

    # Login as new user — must_change_password should be true
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "newuser@test.com", "password": "temppass123"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["must_change_password"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PATH="/opt/homebrew/bin:$PATH" uv run --project backend pytest backend/tests/test_change_password.py::test_create_user_with_must_change_password -v`
Expected: FAIL — `must_change_password` not in login response or not set

- [ ] **Step 3: Update the create_user handler**

In `backend/app/routes/users.py`, modify `create_user` (line 34-67). Add `must_change_password` to the user creation:

```python
@post("/")
async def create_user(data: dict, request: Request, session: AsyncSession) -> Response:
    require_admin(request)
    from app.models.user import User

    email = data.get("email", "").strip().lower()
    display_name = data.get("display_name", "").strip()
    role = data.get("role", "reader")
    password = data.get("password")
    must_change = data.get("must_change_password", False) and password

    if not email or not display_name:
        return Response(content={"detail": "email and display_name required"}, status_code=400)

    user = User(
        email=email,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password) if password else None,
        must_change_password=bool(must_change),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return Response(
        content={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_active": user.is_active,
            "google_oauth_enabled": user.google_oauth_enabled,
        },
        status_code=201,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PATH="/opt/homebrew/bin:$PATH" uv run --project backend pytest backend/tests/test_change_password.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/users.py backend/tests/test_change_password.py
git commit -m "feat: support must_change_password flag in user creation"
```

---

### Task 4: Frontend — API Types & Functions

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Update AuthUser type**

In `frontend/src/api/client.ts`, find the `AuthUser` interface (around line 272) and replace:

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

- [ ] **Step 2: Add changePassword API function**

In the `api.auth` object, add after the `setup` function:

```typescript
    changePassword: (currentPassword: string, newPassword: string) =>
      request<LoginResponse>("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      }),
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add must_change_password to AuthUser and changePassword API function"
```

---

### Task 5: Frontend — AuthContext `updateUser` Helper

**Files:**
- Modify: `frontend/src/auth/AuthContext.tsx`

- [ ] **Step 1: Add `updateUser` to AuthState and provider**

In `frontend/src/auth/AuthContext.tsx`, add `updateUser` to the `AuthState` interface:

```typescript
interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  logout: () => Promise<void>;
  setup: (data: {
    email: string;
    password: string;
    display_name: string;
    club_name: string;
    club_short: string;
  }) => Promise<void>;
  updateUser: (user: AuthUser) => void;
}
```

Add the callback in the provider body (after `setup`):

```typescript
  const updateUser = useCallback((u: AuthUser) => {
    setUser(u);
  }, []);
```

Update the provider value:

```typescript
      value={{ user, loading, login, loginWithGoogle, logout, setup, updateUser }}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/auth/AuthContext.tsx
git commit -m "feat: add updateUser to AuthContext for password change flow"
```

---

### Task 6: Frontend — Profile Page

**Files:**
- Create: `frontend/src/pages/ProfilePage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create ProfilePage**

Create `frontend/src/pages/ProfilePage.tsx`:

```typescript
import { useState } from "react";
import { api, setAccessToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function ProfilePage() {
  const { user, updateUser } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!user) return null;

  if (!user.has_password) {
    return (
      <div>
        <h1 className="font-headline text-2xl font-bold text-on-surface mb-4">
          Mon compte
        </h1>
        <p className="text-sm text-on-surface-variant">
          Vous utilisez Google pour vous connecter. La modification du mot de passe n'est pas disponible.
        </p>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);

    if (newPassword !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas");
      return;
    }
    if (newPassword.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères");
      return;
    }

    setLoading(true);
    try {
      const resp = await api.auth.changePassword(currentPassword, newPassword);
      setAccessToken(resp.access_token);
      updateUser(resp.user);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("401")) {
        setError("Mot de passe actuel incorrect");
      } else {
        setError("Une erreur est survenue");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="font-headline text-2xl font-bold text-on-surface mb-6">
        Mon compte
      </h1>

      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6 max-w-md">
        <h2 className="font-headline font-bold text-on-surface text-sm mb-4">
          Changer le mot de passe
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-on-surface-variant mb-1">
              Mot de passe actuel
            </label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-on-surface-variant mb-1">
              Nouveau mot de passe
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-on-surface-variant mb-1">
              Confirmer le nouveau mot de passe
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
              required
            />
          </div>

          {error && (
            <p className="text-xs text-error">{error}</p>
          )}
          {success && (
            <p className="text-xs text-primary font-semibold">
              Mot de passe modifié avec succès
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold disabled:opacity-50"
          >
            {loading ? "..." : "Changer le mot de passe"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add route and navigation**

In `frontend/src/App.tsx`:

Add the import at the top with the other page imports:
```typescript
import ProfilePage from "./pages/ProfilePage";
```

In `getPageTitle()` (around line 25-34), add before the final `return ""`:
```typescript
  if (pathname === "/profil") return "Mon compte";
```

In the Routes section inside `AuthenticatedLayout` (around line 151-166), add before the `</Routes>`:
```typescript
            <Route path="/profil" element={<ProfilePage />} />
```

Replace the user name display in the sidebar (lines 121-125) — change the `<div>` and `<span>` to a link:

Current:
```typescript
          <div className="flex items-center gap-2 px-4 py-2">
            <span className="material-symbols-outlined text-on-surface-variant text-xl">account_circle</span>
            <span className="text-xs text-on-surface-variant truncate flex-1">
              {user?.display_name || user?.email}
            </span>
```

Replace with:
```typescript
          <div className="flex items-center gap-2 px-4 py-2">
            <span className="material-symbols-outlined text-on-surface-variant text-xl">account_circle</span>
            <Link
              to="/profil"
              onClick={closeSidebar}
              className="text-xs text-on-surface-variant hover:text-on-surface truncate flex-1 transition-colors"
            >
              {user?.display_name || user?.email}
            </Link>
```

Add `Link` to the existing react-router-dom import (line 2) if not already there. It should already be imported since `NavLink` is used from the same package. Check the import line — it currently imports `{ Routes, Route, NavLink, useLocation, Navigate }`. Add `Link`:

```typescript
import { Routes, Route, NavLink, Link, useLocation, Navigate } from "react-router-dom";
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ProfilePage.tsx frontend/src/App.tsx
git commit -m "feat: add profile page with password change form"
```

---

### Task 7: Frontend — Force Password Change Modal

**Files:**
- Create: `frontend/src/components/ForcePasswordModal.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create the modal component**

Create `frontend/src/components/ForcePasswordModal.tsx`:

```typescript
import { useState, useEffect } from "react";
import { api, setAccessToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";

interface Props {
  onClose: () => void;
}

export default function ForcePasswordModal({ onClose }: Props) {
  const { user, updateUser } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  if (!user) return null;

  // OAuth-only users: just show info and close button
  if (!user.has_password) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
        <div className="absolute inset-0 bg-on-surface/40" />
        <div className="relative bg-surface rounded-2xl shadow-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
          <h2 className="font-headline font-bold text-on-surface text-base mb-2">
            Changement de mot de passe requis
          </h2>
          <p className="text-sm text-on-surface-variant mb-4">
            Vous utilisez Google pour vous connecter. La modification du mot de passe n'est pas disponible.
          </p>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold"
          >
            Fermer
          </button>
        </div>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (newPassword !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas");
      return;
    }
    if (newPassword.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères");
      return;
    }

    setLoading(true);
    try {
      const resp = await api.auth.changePassword(currentPassword, newPassword);
      setAccessToken(resp.access_token);
      updateUser(resp.user);
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("401")) {
        setError("Mot de passe actuel incorrect");
      } else {
        setError("Une erreur est survenue");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-on-surface/40" />
      <div className="relative bg-surface rounded-2xl shadow-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-headline font-bold text-on-surface text-base">
            Changement de mot de passe requis
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>
        <p className="text-sm text-on-surface-variant mb-4">
          Un administrateur a demandé que vous changiez votre mot de passe.
        </p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="password"
            placeholder="Mot de passe actuel"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
            required
          />
          <input
            type="password"
            placeholder="Nouveau mot de passe"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
            required
          />
          <input
            type="password"
            placeholder="Confirmer le nouveau mot de passe"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
            required
          />

          {error && <p className="text-xs text-error">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold disabled:opacity-50"
          >
            {loading ? "..." : "Changer le mot de passe"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire the modal into AuthenticatedLayout**

In `frontend/src/App.tsx`:

Add the import:
```typescript
import ForcePasswordModal from "./components/ForcePasswordModal";
```

Inside `AuthenticatedLayout`, add state and dismiss logic after the existing state declarations (after `const [sidebarOpen, setSidebarOpen] = useState(false);`):

```typescript
  const [passwordModalDismissed, setPasswordModalDismissed] = useState(
    () => sessionStorage.getItem("password_change_dismissed") === "true"
  );

  const showPasswordModal =
    user?.must_change_password === true && !passwordModalDismissed;

  function dismissPasswordModal() {
    sessionStorage.setItem("password_change_dismissed", "true");
    setPasswordModalDismissed(true);
  }
```

Add the warning dot next to the user name in the sidebar. Find the `<Link to="/profil"` that was added in Task 6 and add the dot after it:

```typescript
            <Link
              to="/profil"
              onClick={closeSidebar}
              className="text-xs text-on-surface-variant hover:text-on-surface truncate flex-1 transition-colors"
            >
              {user?.display_name || user?.email}
            </Link>
            {user?.must_change_password && (
              <span className="w-2 h-2 rounded-full bg-orange-500 shrink-0" title="Changement de mot de passe requis" />
            )}
```

Add the modal render at the very end of the `AuthenticatedLayout` return, just before the closing `</JobProvider>`:

```typescript
      {showPasswordModal && (
        <ForcePasswordModal onClose={dismissPasswordModal} />
      )}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ForcePasswordModal.tsx frontend/src/App.tsx
git commit -m "feat: add force password change modal with dismissal and warning dot"
```

---

### Task 8: Frontend — Admin Checkbox in SettingsPage

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Add `must_change_password` to the user creation form state**

In `frontend/src/pages/SettingsPage.tsx`, find the `newUser` state (line 59-64):

Current:
```typescript
  const [newUser, setNewUser] = useState({
    email: "",
    display_name: "",
    role: "reader",
    password: "",
  });
```

Replace with:
```typescript
  const [newUser, setNewUser] = useState({
    email: "",
    display_name: "",
    role: "reader",
    password: "",
    must_change_password: false,
  });
```

Update the reset in `createUser` `onSuccess` (line 71):

Current:
```typescript
      setNewUser({ email: "", display_name: "", role: "reader", password: "" });
```

Replace with:
```typescript
      setNewUser({ email: "", display_name: "", role: "reader", password: "", must_change_password: false });
```

- [ ] **Step 2: Add the checkbox in the form**

In `SettingsPage.tsx`, after the password input (line 339, after the closing `/>` of the password input), add:

```typescript
            {newUser.password && (
              <label className="flex items-center gap-2 text-xs text-on-surface-variant">
                <input
                  type="checkbox"
                  checked={newUser.must_change_password}
                  onChange={(e) =>
                    setNewUser((u) => ({ ...u, must_change_password: e.target.checked }))
                  }
                  className="rounded"
                />
                Forcer le changement au prochain login
              </label>
            )}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add must_change_password checkbox in admin user creation form"
```

---

### Task 9: Final Verification

**Files:**
- Various — verification only

- [ ] **Step 1: Run full backend tests**

Run: `PATH="/opt/homebrew/bin:$PATH" uv run --project backend pytest backend/tests/ -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 2: Build frontend**

Run: `PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: Build succeeds

- [ ] **Step 3: TypeScript check**

Run: `PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit`
Expected: No errors
