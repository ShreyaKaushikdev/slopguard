# Deployment

SlopGuard can be demoed locally, through Docker Compose, or as separate Vercel
and Railway services.

## Local

Terminal 1:

```powershell
cd apps/api
pip install -r requirements.txt
uvicorn slopguard.main:app --reload --port 8000
```

Terminal 2:

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://127.0.0.1:3000`.

## Docker Compose

```powershell
docker-compose up --build
```

Open:

- Dashboard: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`

## Extension

1. Start the API.
2. Open Chrome `chrome://extensions`.
3. Enable Developer Mode.
4. Click **Load unpacked**.
5. Select `apps/extension`.

For GitHub PRs, SlopGuard reads the PR title, description, and `.diff` view,
then calls `/score/pr`. Other pages use `/score/text` with a domain adapter
selected from the hostname.

## Hosted Split

Recommended production-style split:

- `apps/web` on Vercel.
- `apps/api` on Railway, Render, or Fly.io.
- Set `NEXT_PUBLIC_API_URL` in the web deployment to the API URL.

