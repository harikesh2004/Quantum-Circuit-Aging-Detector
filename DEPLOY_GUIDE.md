# 🚀 Deployment Guide

## Step 1: Create GitHub Repository

1. Go to **https://github.com/new**
2. Repository name: `qagenet` (or any name you prefer)
3. Description: `Quantum Circuit Aging Detection System with ML-powered anomaly detection`
4. **Keep it Public** (required for free Vercel hosting)
5. **Do NOT** initialize with README, .gitignore, or license
6. Click **Create repository**

## Step 2: Push to GitHub

Run these commands in PowerShell (already in D:\QC-2):

```bash
# Add your GitHub repository as remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/qagenet.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

**Example** (replace `harikesh2004` with your GitHub username):
```bash
git remote add origin https://github.com/harikesh2004/qagenet.git
git branch -M main
git push -u origin main
```

You'll be prompted to authenticate with GitHub.

## Step 3: Deploy to Vercel

### Option A: Import from GitHub (Recommended)
1. Go to **https://vercel.com/new**
2. Sign in with GitHub
3. Click **Import Project**
4. Select your `qagenet` repository
5. Configure:
   - **Framework Preset**: Other
   - **Root Directory**: `./` (leave as default)
   - **Build Command**: (leave empty)
   - **Output Directory**: `.` (leave as default)
6. Click **Deploy**

Your dashboard will be live at: `https://qagenet-[random].vercel.app`

### Option B: Vercel CLI
```bash
npm install -g vercel
cd D:\QC-2
vercel --prod
```

## What Gets Deployed?

**On Vercel (Static Mode)**:
- ✅ Full dashboard UI with pre-computed results
- ✅ Interactive charts and metrics
- ✅ Professional dark theme
- ❌ "Run Simulation" button won't work (requires local Qiskit)

The dashboard will display the JSON results already in your repo, making it perfect for presentations and sharing.

## Local Development

**To run locally with full simulation support**:
```bash
# Activate virtual environment
qagenet_env\Scripts\activate

# Start Flask server
python app.py

# Open browser
http://localhost:5000
```

## Repository Structure

```
qagenet/
├── index.html                    # Main dashboard
├── app.py                        # Flask backend (local only)
├── static/
│   ├── css/styles.css           # Dark quantum theme
│   └── js/app.js                # Frontend logic + Chart.js
├── quantum_aging_detector*.py    # Quantum models
├── qagenet_results_*.json       # Pre-computed results
├── vercel.json                  # Vercel config
├── .gitignore                   # Excludes venv, cache
└── README.md                    # Documentation
```

## Future Updates

To push updates:
```bash
git add .
git commit -m "Your update message"
git push
```

Vercel will auto-deploy on every push to `main`.

## Troubleshooting

**Push rejected**: If you get authentication errors, use:
```bash
git remote set-url origin https://YOUR_USERNAME@github.com/YOUR_USERNAME/qagenet.git
```

**Vercel build fails**: Ensure `vercel.json` exists and `index.html` is in the root directory.

**Charts not showing**: Check browser console. May need to reload after first deploy.

---

🎉 Your quantum research dashboard is now version-controlled and ready to share!
