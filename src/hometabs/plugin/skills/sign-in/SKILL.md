---
name: sign-in
description: Use whenever a task needs signing in to a website (a login page, username/password fields, "log in for me"), even if the user doesn't mention a password manager. Says how to sign in with the browser's password manager autofill.
---
# Signing in to websites

Sign in with the password manager's autofill in the browser. If the `1password`
skill is available, load it and follow its autofill and unlock steps.

- Never type a password, one-time code or other secret yourself, and never
  repeat credentials in your reply.
- 1Password's autofill menu is an iframe at the bottom of the snapshot. Click a
  menu item by its snapshot ref: `await page.click('<ref>')` with the actual
  ref. `frameLocator(...)` and `aria-ref=` locators can't reach that menu.
- If the menu closes before you click, click the form field again and take a
  new snapshot.
- If no password manager can fill the form, ask the user to sign in themselves.
