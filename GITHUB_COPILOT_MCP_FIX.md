# GitHub Copilot MCP Configuration Fix Guide

## Issues Found in Current settings.json

1. **Malformed JSON structure**
   - Missing commas between objects
   - Incomplete tool configurations
   - Random properties mixed in (like "Log": true, "indentationMode": true)
   - Broken nesting structure

2. **Incorrect MCP tool format**
   - Tools are not properly configured for VS Code MCP format
   - Mixing GitHub Copilot chat tools with MCP servers
   - Missing required fields for MCP server configuration

3. **Account Issues**
   - Need to sign out and switch GitHub account

## Step 1: Sign Out and Switch GitHub Account

### Method 1: Using VS Code Accounts Menu (Recommended)
1. Click the **Accounts** icon in the Activity Bar (bottom left)
2. Find your current GitHub account
3. Click **Sign out** for that account
4. Clear browser cache/cookies for github.com
5. Sign in with the correct GitHub account using one of:
   - Click **Sign in to use Copilot** from the Copilot status menu
   - Use Command Palette: `Ctrl+Shift+P` → `GitHub Copilot: Sign in`
   - Click Accounts menu → **Sign in with GitHub to use GitHub Copilot**

### Method 2: If Method 1 Doesn't Work
1. Uninstall GitHub Copilot extension
2. Clear VS Code cache:
   - Windows: `%APPDATA%\Code\Cache` and `%APPDATA%\Code\CachedData`
   - Linux: `~/.config/Code/Cache` and `~/.config/Code/CachedData`
   - Mac: `~/Library/Application Support/Code/Cache`
3. Restart VS Code
4. Reinstall GitHub Copilot extension
5. Sign in with correct account

## Step 2: Create Proper MCP Configuration

Create a new file `.vscode/mcp.json` in your workspace (NOT in settings.json):

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "smithery-key",
      "description": "Smithery API Key",
      "password": true,
      "default": "f14cef5c-b856-454f-bf01-7cf75df918c5"
    },
    {
      "type": "promptString",
      "id": "smithery-profile",
      "description": "Smithery Profile",
      "default": "geographical-eagle-karTUD"
    }
  ],
  "servers": {
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@upstash/context7-mcp",
        "--key",
        "${input:smithery-key}"
      ]
    },
    "sequentialThinking": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@smithery-ai/server-sequential-thinking",
        "--key",
        "${input:smithery-key}"
      ]
    },
    "codeInterpreter": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@waldzellai/clear-thought",
        "--key",
        "${input:smithery-key}"
      ]
    },
    "memoryTool": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@mem0ai/mem0-memory-mcp",
        "--key",
        "${input:smithery-key}",
        "--profile",
        "${input:smithery-profile}"
      ]
    },
    "toolbox": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@smithery/toolbox",
        "--key",
        "${input:smithery-key}",
        "--profile",
        "${input:smithery-profile}"
      ]
    },
    "desktopCommander": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@wonderwhy-er/desktop-commander",
        "--key",
        "${input:smithery-key}"
      ]
    },
    "thinkTool": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@PhillipRt/think-mcp-server",
        "--key",
        "${input:smithery-key}"
      ]
    },
    "memoryBank": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@ipospelov/mcp-memory-bank",
        "--key",
        "${input:smithery-key}"
      ]
    },
    "codeMcp": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@block/code-mcp",
        "--key",
        "${input:smithery-key}"
      ]
    },
    "perplexityChat": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@daniel-lxs/mcp-perplexity",
        "--key",
        "${input:smithery-key}",
        "--profile",
        "${input:smithery-profile}"
      ]
    },
    "firecrawl": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@Krieg2065/firecrawl-mcp-server",
        "--key",
        "${input:smithery-key}",
        "--profile",
        "${input:smithery-profile}"
      ]
    },
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@smithery-ai/github",
        "--key",
        "${input:smithery-key}",
        "--profile",
        "${input:smithery-profile}"
      ]
    }
  }
}
```

## Step 3: Clean Up settings.json

Your settings.json should be cleaned up to remove the malformed MCP configurations. Here's what should remain:

```json
{
    "codeium.enableConfig": {
        "*": true
    },
    "codeium.enableSearch": true,
    "github.copilot.nextEditSuggestions.enabled": true,
    "chat.mcp.discovery.enabled": true,
    "redhat.telemetry.enabled": false,
    "github.copilot.advanced": {},
    "github.copilot.chat.reviewSelection.instructions": [
        {"text": "Use underscore for field names."},
        {"text": "ALWAYS RESEARCH BEFORE ADDING CODE TO THE REPOSITORY."},
        {"text": "GET CONTEXT IF CODE CAUSES ERRORS."}, 
        {"text": "read the .md left by other coder to understand if there are new changes that were made."},
        {"text": "ALWAYS ASK FOR HELP IF YOU DON'T UNDERSTAND SOMETHING."},
        {"text": "document all changes when done making them in the CHANGES.md file."},
        {"text": "ask if the changes need to be committed or not to github."}
    ],
    "github.copilot.chat.reviewSelection.enabled": true,
    "github.copilot.chat.agent.thinkingTool": true,
    "files.autoSave": "afterDelay",
    "github.copilot.enable": {
        "markdown": true,
        "scminput": true
    },
    "github.copilot.chat.scopeSelection": true,
    "github.copilot.chat.codesearch.enabled": true,
    "github.copilot.chat.completionContext.typescript.mode": "on",
    "githubPullRequests.experimental.chat": true,
    "githubPullRequests.experimental.useQuickChat": true,
    "github.copilot.chat.languageContext.fix.typescript.enabled": true,
    "github.copilot.chat.languageContext.inline.typescript.enabled": true,
    "github.copilot.chat.languageContext.typescript.enabled": true,
    "python.jediEnabled": false,
    "python.linting.pylintEnabled": true,
    "python.analysis.typeCheckingMode": "standard",
    "python.analysis.diagnosticSeverityOverrides": {},
    "gitConfigUser.profiles": [
        {
            "label": "schech",
            "email": "ceo@schechtercustoms.com",
            "userName": "schech",
            "selected": true
        },
        {
            "label": "AI Agent",
            "userName": "AI Agent",
            "email": "agent@ai.com",
            "selected": true
        }
    ],
    "workbench.colorTheme": "New Darcula",
    "extensions.experimental.affinity": {
        "asvetliakov.vscode-neovim": 1
    },
    "git.openRepositoryInParentFolders": "never",
    "terminal.explorerKind": "both",
    "terminal.integrated.copyOnSelection": true,
    "terminal.integrated.cursorBlinking": true,
    "terminal.integrated.cursorStyle": "line",
    "terminal.integrated.cursorStyleInactive": "block",
    "terminal.integrated.cursorWidth": 3,
    "terminal.integrated.defaultProfile.linux": "bash",
    "terminal.integrated.focusAfterRun": "terminal",
    "terminal.integrated.gpuAcceleration": "on",
    "terminal.integrated.localEchoEnabled": "auto",
    "terminal.integrated.rightClickBehavior": "selectWord",
    "terminal.integrated.shellIntegration.environmentReporting": true,
    "terminal.integrated.smoothScrolling": true,
    "terminal.integrated.stickyScroll.enabled": true,
    "terminal.integrated.suggest.enabled": true
}
```

## Step 4: Verify Configuration

1. **Check MCP servers are loaded**:
   - Open Command Palette: `Ctrl+Shift+P`
   - Run: `MCP: List Servers`
   - You should see all configured servers

2. **Test in Agent Mode**:
   - Open Chat: `Ctrl+Alt+I` (Windows/Linux) or `⌃⌘I` (Mac)
   - Switch to **Agent mode** from dropdown
   - Click **Tools** button to see available MCP tools

3. **Check GitHub account**:
   - Click Accounts icon in Activity Bar
   - Verify correct GitHub account is shown
   - Check Copilot status in status bar

## Step 5: Update API Key (if needed)

If you need to use a different API key:
1. Update the `default` value in `.vscode/mcp.json` for `smithery-key`
2. Or leave it blank to be prompted each time
3. Consider using environment variables for sensitive keys

## Troubleshooting

If MCP servers don't start:
1. Check VS Code Output panel → MCP Servers
2. Verify `npx` is available in PATH
3. Ensure internet connection for package downloads
4. Try restarting VS Code after configuration

If GitHub account issues persist:
1. Completely uninstall VS Code
2. Delete all VS Code data folders
3. Reinstall VS Code
4. Install GitHub Copilot extension fresh
5. Sign in with correct account

## Security Notes

- Never commit API keys to version control
- Use `.gitignore` to exclude `.vscode/mcp.json` if it contains sensitive data
- Consider using environment variables or VS Code's secure input prompts
- Review MCP server permissions before enabling