---
name: 1password
description: Use whenever a task needs signing in to a website (a login page, username or password fields, "log in for me"), even if the user doesn't mention 1Password. Explains how to autofill logins from the user's 1Password extension and what to do when it's locked.
icon: https://static.asidehq.com/apps/builtin-skills/1password.jpg
---
# 1Password

## How to autofill

1Password autofill options appear as an iframe popover menu after focusing a form field.

1. Click the form you want to autofill.
2. Wait 500ms, up to 1 second, for the menu to appear.
3. Take a snapshot.

Then check whether the bottom of the snapshot includes `iframe [origin="1Password"]`.

1. If the iframe autofill menu is shown and it has an appropriate item for the task, use it.
   Click the item by its ref from the `iframe [origin="1Password"]` part of the snapshot: `await page.click('f1e1')` (use the actual ref). `frameLocator(...)` and `aria-ref=` locators can't reach this menu. If the menu closes, click the field again and take a new snapshot.
2. If the iframe autofill menu is not shown, but `status: "1Password menu is available. Press down arrow to select."` is shown, 1Password is locked. Follow the unlock flow below.
3. If neither the iframe autofill menu nor the status is shown, 1Password is not available for the form.

## When 1Password is locked

Open the 1Password extension page only to unlock 1Password using the password saved on this device:

`chrome-extension://aeblfdkhhhdcdjpifhhbdiojplfjncoa/popup/index.html`

Read `externalPasswordManagers.list()` to check whether this provider has an unlock password on this device. Take a fresh snapshot of the extension page and select its editable password input ref, then call:

```js
await externalPasswordManagers.autofillUnlockPassword(page, '1password', 'e12'); // use the actual fresh password ref
```

The explicit provider must match the extension. The result confirms submission only: inspect a fresh snapshot to verify unlock before continuing. Do not retry a failed submission automatically.

After unlocking 1Password:

1. Return to the original sign-in page.
2. Close the 1Password extension tab opened only for unlocking.
3. **IMPORTANT: Refresh the original sign-in page.** Unless you won't see the 1Password menu.
4. Click the form field again to reopen the autofill menu.
5. Continue from the 1Password menu on the original sign-in page.

Do not use the 1Password extension page as the primary place to search and autofill website logins.
Use the original sign-in page's 1Password autofill menu for website login autofill.

If no unlock password is saved, ask the user to unlock this provider directly. Do not initialize Aside Password Manager or use another provider's credential. External unlock works independently of Aside Password Manager's setup, lock state and agent access settings.
