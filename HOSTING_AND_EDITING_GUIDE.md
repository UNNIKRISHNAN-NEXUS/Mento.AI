# 🚀 Mento.AI — Vercel Hosting & Post-Deployment Editing Guide

This guide details how to publish your **Mento.AI** web application to **Vercel** and how to easily edit the website after hosting.

---

## 🛠 Project Configuration Overview
The following Vercel configuration files have been created in your project:
- **`vercel.json`**: Directs API requests to Python serverless functions (`api/index.py`) and static assets to `frontend/`.
- **`api/index.py`**: Vercel Python serverless entrypoint importing the FastAPI application.
- **`requirements.txt`**: List of dependencies for Vercel's automated cloud build.
- **`.vercelignore`**: Excludes local virtual environments (`backend/.venv`) and temporary upload files from build uploads.

---

## 🌐 1. How to Host/Publish on Vercel

### Option A: Using Vercel CLI (Quickest Method)
1. Open your terminal or command prompt in the project root:
   ```cmd
   cd D:\Mento.AI
   ```
2. Run the Vercel deployment command:
   ```cmd
   npx vercel
   ```
3. Follow the quick terminal prompts:
   - **Set up and deploy?**: `y`
   - **Which scope?**: Select your Vercel account.
   - **Link to existing project?**: `n`
   - **Project Name**: `mento-ai` (or your choice).
   - **Directory located**: `./`
4. Once deployed, run the production command to get your live URL:
   ```cmd
   npx vercel --prod
   ```

---

### Option B: Using GitHub + Vercel Dashboard (Best for Continuous Editing)
1. Upload/Push the project folder `D:\Mento.AI` to a repository on your **GitHub** account.
2. Go to **[https://vercel.com/new](https://vercel.com/new)** and log in.
3. Click **Import** next to your `Mento.AI` repository.
4. Click **Deploy**. Vercel will automatically build and publish your site!

---

## ✏️ 2. How to Edit the Website After Hosting

After your site is hosted, you can edit it at any time:

### Editing Frontend Code (UI, Styling, Logic)
- **Files to edit**:
  - `frontend/index.html` — Layout, text, headers, dropzones, and buttons.
  - `frontend/css/style.css` — Colors, typography, responsive styles, animations.
  - `frontend/js/app.js` — Frontend state, event handlers, file selection, API calls.

### Editing Backend Code (Python Processing & Document Generation)
- **Files to edit**:
  - `backend/main.py` — API routes, upload handlers, and pipeline parameters.
  - `backend/core/docx_generator.py` — Document formatting, Times New Roman styles, and PDF generation logic.

---

### 🔄 How to Publish Your Edits Live

#### If using GitHub:
Every time you make edits locally, simply push your changes:
```cmd
git add .
git commit -m "Updated website styling and UI text"
git push origin main
```
**Vercel will automatically detect your push and re-deploy the new version live in ~15 seconds!**

#### If using Vercel CLI:
Simply run:
```cmd
npx vercel --prod
```
Your edits will be published live instantly.
