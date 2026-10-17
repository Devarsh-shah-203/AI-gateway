# AI Gateway — Setup Guide

This guide takes you from a fresh Windows machine to running AI Gateway in your terminal.

AI Gateway is being designed to work with different browser-based AI providers. **For now, only ChatGPT is supported and tested**; Claude, Gemini, and other providers are not currently supported.

The normal workflow is:

1. Install Python.
2. Get the AI Gateway project.
3. Create and activate a `.venv` virtual environment.
4. Install the packages listed in `requirements.txt`.
5. Find the location of `chrome.exe` using `chrome://version`.
6. Start Chrome with remote debugging enabled.
7. Sign in to ChatGPT in that Chrome window.
8. Run `main.py` from a second terminal.

## 1. Install Python

Download Python for Windows from the official website:

https://www.python.org/downloads/

Install a stable Python 3 release supported by the dependencies in this repository. Make sure the Python commands are available from your terminal.

Open **Command Prompt** and verify the installation:

```bat
python --version
py --version
```

At least one of these commands should display the installed Python version. If neither command works, finish the Python installation and reopen Command Prompt before continuing.

## 2. Get the AI Gateway project

If Git is installed, clone the repository:

```bat
git clone https://github.com/Devarsh-shah-203/AI-gateway.git
cd AI-gateway
```

If you downloaded the repository as a ZIP instead, extract it and open Command Prompt in the extracted folder.

**Important:** Run the remaining project commands from the repository root—the folder that contains `main.py` and `requirements.txt`.

Confirm the files are there:

```bat
dir
```

You should see `main.py` and `requirements.txt` in the listing.

## 3. Create a virtual environment

A virtual environment keeps AI Gateway's Python packages separate from other Python projects on your machine.

From the repository root, run:

```bat
py -m venv .venv
```

If `py` is not available but `python` works, use:

```bat
python -m venv .venv
```

This creates a `.venv` directory inside the repository. You only need to create it once for this project.

## 4. Activate `.venv`

In **Command Prompt**, run:

```bat
.venv\Scripts\activate.bat
```

After activation, the prompt should begin with `(.venv)`.

If you are using **PowerShell**, run:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use the Command Prompt instructions instead; you do not need to change your machine-wide execution policy just to set up this project.

Verify that Python is available in the environment:

```bat
python --version
python -m pip --version
```

Keep the virtual environment activated in the terminal where you install dependencies and run AI Gateway.

## 5. Install the dependencies from `requirements.txt`

The repository's dependency file is named **`requirements.txt`** (with an `s` at the end). It lists the Python packages and versions required by the project.

With `.venv` activated, run:

```bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Wait for pip to finish, then check for dependency issues:

```bat
python -m pip check
```

If the command reports that there are no broken requirements, the installed packages are consistent.

### Do I need to run `playwright install`?

The current gateway connects to an already-running Google Chrome instance through Chrome DevTools Protocol (CDP). For this normal workflow, install Google Chrome separately and install the Python packages from `requirements.txt`; a Playwright-managed browser download is not normally needed.

If the code changes in the future to launch a Playwright-managed browser, follow the updated project instructions for installing its browser binaries.

## 6. Find `chrome.exe` and start Chrome with remote debugging

AI Gateway connects to Chrome at:

```text
http://127.0.0.1:9222
```

Chrome may be installed in a different location on each computer. Instead of assuming the executable path, find it from Chrome itself:

1. Open Google Chrome normally.
2. Type `chrome://version` in the address bar and press **Enter**.
3. Find the **Executable Path** field on the page.
4. Copy the full path to `chrome.exe`.
5. Close the Chrome window before launching the dedicated profile below, especially if you plan to use the same profile directory.

Open **Command Prompt** in the AI Gateway repository root and run the following command, replacing the example executable path with the path you copied:

```bat
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%CD%\chrome-data"
```

For example, if `chrome://version` shows a different executable location, use that location while keeping the command-line options unchanged. Keep the executable path inside double quotes, especially if it contains spaces.

This command uses a dedicated `chrome-data` profile inside the repository. The project `.gitignore` excludes this directory; still, never commit or share browser-profile data because it may contain authenticated sessions.

**Important:**
- Keep this Chrome window open while AI Gateway is running.
- Do not start a second Chrome instance using the same `chrome-data` profile while the first instance is using it.
- If you already started Chrome using this remote-debugging profile, use that window rather than starting another copy with the same profile.
- Do not assume that an ordinary Chrome window is the remote-debugging instance. Use the command above to start the dedicated instance.

### Sign in to the currently supported provider: ChatGPT

AI Gateway is intended to become provider-agnostic, so it can eventually work with different browser-based AI models. **The current implementation supports ChatGPT only**; do not assume Claude, Gemini, or another provider will work yet.

In the Chrome window started by the command:

1. Open the ChatGPT website.
2. Sign in to your account if needed.
3. Open a conversation and wait until the chat composer is available.

You need your own access to the browser-based service. AI Gateway does not supply an account, subscription, or API key.

### Check the remote-debugging connection

With the remote-debugging Chrome window open, visit this local address in a browser:

http://127.0.0.1:9222/json/version

If the endpoint responds with JSON describing the browser, Chrome's debugging endpoint is reachable. If it does not load, check the Chrome command and port before starting AI Gateway.

## 7. Run AI Gateway

Leave the remote-debugging Chrome window open. Open a **second Command Prompt** window and change to the AI Gateway repository directory.

For example, if you cloned the repository into your user folder:

```bat
cd "%USERPROFILE%\AI-gateway"
```

Use the actual path where you saved the project. Then activate the existing environment and start the application:

```bat
.venv\Scripts\activate.bat
python main.py
```

The gateway should attempt to connect to Chrome and locate the open ChatGPT interface. Follow any status or error message displayed in the terminal.

### Send your first prompt

Once the CLI is running, enter a normal request, for example:

```text
Explain what this project does and how its main modules work.
```

The gateway sends the request to ChatGPT in the browser and displays the completed response in the terminal.

## 8. Configure a project workspace

To provide file context from one of your own projects, register its directory. Use a directory that already exists and is outside the AI Gateway repository.

Example:

```text
/workspace add "D:\Projects\my-app"
```

View the configured workspace and its numeric ID:

```text
/workspace
```

If the workspace is assigned ID `1`, you can reference a project file in a prompt like this:

```text
Explain the authentication flow in <1/src/auth.js>
```

Use the actual workspace ID and relative file path for your project. File references must be wrapped in angle brackets and use the form `<workspace_id/relative/path>`.

## 9. Try the main workflows

### Ask a question about a file

```text
Explain the responsibilities of <1/src/auth.js> and identify possible edge cases.
```

### Request an edit

Enter edit mode:

```text
/edit
```

Then describe the change and reference the file:

```text
Add input validation to <1/src/auth.js> while preserving existing behavior.
```

Inspect the proposed edit and its explanation. Approve it only if the change is correct. Use `/cancel` to leave edit mode.

### Use project memory

The memory feature is controlled by commands:

| Command | Purpose |
| --- | --- |
| `/memory use` | Include project memory in the next normal prompt only. |
| `/memory on` | Enable memory mode. |
| `/memory off` | Disable future memory injection. |
| `/memory refresh` | Queue a fresh inclusion of the memory snapshot. |
| `/save` | Ask the current conversation to identify durable project knowledge and save a validated proposal locally. |

Project memory is local by default and is not automatically attached to every prompt. Review the README for the complete command reference and the behavior of each memory mode.

**Note:** `/commands` is planned but is not implemented in the current CLI yet.

## 10. What to do next time you use AI Gateway

After the initial setup, you do **not** need to recreate `.venv` or reinstall packages every time.

For each new working session:

1. Start Chrome with the same remote-debugging command and `chrome-data` profile.
2. Open ChatGPT in that Chrome window and confirm you are signed in.
3. Open Command Prompt in the AI Gateway repository.
4. Activate `.venv`.
5. Run `python main.py`.

The recurring terminal commands are:

```bat
.venv\Scripts\activate.bat
python main.py
```

If `requirements.txt` changes after you update or pull the repository, activate `.venv` and rerun:

```bat
python -m pip install -r requirements.txt
```

When finished, enter `/exit` in AI Gateway. You can close the dedicated Chrome window after the gateway has exited.

## Troubleshooting

### `python` or `py` is not recognized

Python may not be installed correctly or may not be available on your terminal's PATH. Finish the official Python installation, open a new terminal, and retry `python --version` or `py --version`.

### `No module named playwright` (or another dependency)

Confirm you are in the repository root and that `.venv` is activated. Then run:

```bat
python -m pip install -r requirements.txt
```

### AI Gateway cannot connect to Chrome

- Confirm Chrome was launched with `--remote-debugging-port=9222`.
- Open `http://127.0.0.1:9222/json/version` and check that it returns browser information.
- Confirm the Chrome window is still open.
- Confirm the gateway is using the same port configured in `browser/connection.py`.
- If the command says Chrome cannot be found, revisit `chrome://version` and copy the exact **Executable Path**.

### The chat interface is not ready

- Open ChatGPT in the dedicated Chrome window. Other providers are not currently supported.
- Sign in if requested.
- Wait until the conversation and input box finish loading.
- Check whether the page displays a usage limit, sign-in prompt, or action that requires your attention.

### Prompt submission or response detection fails

Inspect the browser to see whether the prompt was submitted and whether the model began responding. Do not immediately resend a prompt if the original submission may already have succeeded, because that can create duplicate requests.

### Workspace or file references fail

- Run `/workspace` and confirm the directory exists and has the expected ID.
- Confirm the referenced file is inside that workspace.
- Use angle brackets around each reference, such as `<1/src/app.py>`.

## Security notes

- Use a dedicated Chrome profile for AI Gateway and keep it private.
- Never commit browser session data, cookies, credentials, or access tokens.
- Referencing a local file can send that file's content to the browser-based AI service as prompt context. Only reference files you are permitted to share with that service.
- Review model-generated file changes before approving them.
- Use Git commits or backups before modifying important project files.

## Related documentation

- [README.md](README.md) — what AI Gateway does, its main features, and the current command overview.
- [Python downloads](https://www.python.org/downloads/)
- [Python virtual environments](https://docs.python.org/3/library/venv.html)
- [Playwright for Python](https://playwright.dev/python/docs/intro)
