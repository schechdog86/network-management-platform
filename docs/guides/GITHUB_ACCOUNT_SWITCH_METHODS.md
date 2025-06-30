# GitHub Account Switch Methods - No Accounts Icon

## Method 1: Command Palette (Most Direct)

1. Open Command Palette:
   - **Linux/Windows**: `Ctrl+Shift+P`
   - **Mac**: `Cmd+Shift+P`

2. Type and run these commands in order:
   - `GitHub: Sign Out`
   - `Developer: Reload Window`
   - `GitHub Copilot: Sign In`

## Method 2: Check Status Bar

Look at the bottom right of VS Code's status bar for:
- GitHub icon
- Copilot icon (looks like two overlapping circles)
- Click on either and select "Sign Out"

## Method 3: Settings UI Method

1. Open Settings:
   - `Ctrl+,` (Windows/Linux) or `Cmd+,` (Mac)
   - Or File → Preferences → Settings

2. Search for "github authentication"

3. Look for authentication-related settings and sign out options

## Method 4: Extensions Panel

1. Open Extensions panel:
   - Click Extensions icon in Activity Bar (left side)
   - Or press `Ctrl+Shift+X`

2. Find "GitHub Copilot" extension

3. Click gear icon → Extension Settings

4. Look for sign out or account options

## Method 5: Manual Token Removal

1. Open Command Palette (`Ctrl+Shift+P`)

2. Run: `Preferences: Open User Settings (JSON)`

3. Look for and remove any GitHub-related tokens or authentication entries

4. Also check and clear:
   ```bash
   # Linux
   rm -rf ~/.config/Code/User/globalStorage/github.copilot
   rm -rf ~/.config/Code/User/workspaceStorage/*github*
   
   # Windows
   # Delete folders in:
   # %APPDATA%\Code\User\globalStorage\github.copilot
   # %APPDATA%\Code\User\workspaceStorage\*github*
   ```

## Method 6: Complete Extension Reset

1. Uninstall GitHub Copilot:
   - Extensions panel → GitHub Copilot → Uninstall

2. Clear all VS Code GitHub data:
   ```bash
   # Linux
   rm -rf ~/.config/Code/Cache
   rm -rf ~/.config/Code/CachedData
   rm -rf ~/.config/Code/User/globalStorage/github*
   
   # Windows
   # Delete:
   # %APPDATA%\Code\Cache
   # %APPDATA%\Code\CachedData
   # %APPDATA%\Code\User\globalStorage\github*
   ```

3. Restart VS Code

4. Reinstall GitHub Copilot extension

5. Sign in with correct account

## Method 7: Browser Method

1. Open your default browser

2. Go to https://github.com

3. Sign out of all GitHub accounts

4. Clear cookies for github.com:
   - Chrome: Settings → Privacy → Clear browsing data → Cookies for github.com
   - Firefox: Settings → Privacy → Manage Data → Remove github.com

5. In VS Code, trigger any GitHub action (it will prompt for login)

## Method 8: Check View Menu

Sometimes the Accounts option is hidden:

1. Go to View menu in VS Code menu bar

2. Look for:
   - "Accounts" option
   - "Command Palette" → then search for account options
   - "Appearance" → check if Accounts is hidden

## Method 9: Activity Bar Customization

The Accounts icon might be hidden:

1. Right-click on the Activity Bar (left sidebar)

2. Check if "Accounts" is unchecked

3. Enable it if it's disabled

## Method 10: Direct GitHub Copilot Commands

Try these specific Copilot commands:

1. `Ctrl+Shift+P` to open Command Palette

2. Type and run:
   - `GitHub Copilot: Sign Out`
   - `GitHub Copilot: Manage Copilot Settings`
   - `GitHub Copilot: Open Copilot`

## If All Else Fails

1. Close VS Code completely

2. Navigate to VS Code's data directory and rename it:
   ```bash
   # Linux
   mv ~/.config/Code ~/.config/Code.backup
   
   # Windows
   # Rename: %APPDATA%\Code to %APPDATA%\Code.backup
   ```

3. Start VS Code (it will create fresh config)

4. Install only GitHub Copilot extension

5. Sign in with correct account

6. Restore your other settings gradually from the backup

## Verification

After signing in with the correct account:

1. Check Copilot status in status bar
2. Try using Copilot features
3. Run: `GitHub Copilot: Status` in Command Palette
4. Verify the account shown matches your intended account

## Common Issues

- **"Already signed in"**: Clear all browser cookies for github.com
- **"Invalid token"**: Remove all stored tokens and re-authenticate
- **"No Copilot access"**: Ensure the correct account has Copilot subscription
- **Persistent wrong account**: Full VS Code data reset may be needed