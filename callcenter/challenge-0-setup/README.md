# Challenge 0: Setup & Authentication

Time: ~20 minutes

## Objectives

By the end of this challenge, you will have:

- ✅ A fully provisioned Microsoft Foundry project with a deployed model
- ✅ Application Insights provisioned and connection string available
- ✅ Verified authentication from your local machine to Foundry
- ✅ Confirmed your agent endpoint is working

![setup](./images/setup.png)

## Get Started

There are two ways to get started — pick one:

> **First step for both options:** [Fork this repository](https://github.com/microsoft/FrontierWeekHack/fork) to your own GitHub account.

### Option A: GitHub Codespaces (recommended)

No local installs needed. Everything runs in a cloud dev environment.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/FrontierWeekHack)

After you click the button above, you will see a **Create codespace** prompt. Select these options:

- **Repository:** your forked repo (not `microsoft/FrontierWeekHack`)
- **Branch:** the workshop branch for this event (use the default shown for your fork unless your facilitator says otherwise)
- **Region:** pick your preferred region, or keep the default
- **Machine type:** **2-core**

1. Click the badge above.
2. In the **Create codespace** prompt, select the options listed above, then create the Codespace.
3. Wait for the Codespace to build (~2 min).
4. In the terminal, login to Azure and deploy your scenario:

```bash
az login
```

5. Continue to **Deploy Infrastructure** below.

---

### Option B: Local environment

Run everything on your own machine. Requires Python 3.10+ and Azure CLI.

```bash
# 1. Clone this repo
git clone https://github.com/microsoft/FrontierWeekHack.git
cd FrontierWeekHack

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Login to Azure
az login
```

4. Continue to **Deploy Infrastructure** below.

## Deploy Infrastructure

From the **callcenter** folder, run one of the following depending on your terminal:

| Terminal | Command |
|----------|---------|
| **Bash / macOS / Linux / Codespaces** | `bash challenge-0-setup/deploy.sh` |
| **WSL** | `bash challenge-0-setup/deploy.sh` |
| **Git Bash (Windows)** | `./challenge-0-setup/deploy.sh` |
| **PowerShell (Windows)** | `wsl bash challenge-0-setup/deploy.sh` |

> **Tip:** If you're on Windows without WSL, open the integrated VS Code terminal and switch to **Git Bash** using the dropdown next to the `+` button.

This will provision all resources **and** automatically write your `.env` file to the repository root as `.env`.

## Success Criteria

- [ ] You can see your AI Foundry project in the Azure Portal
- [ ] A model deployment for gpt-5.4 shows "Succeeded" status
- [ ] You can send a test message in the Foundry Playground (Portal)
