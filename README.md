# 3RL

Empty Next.js frontend and FastAPI backend projects.

## Frontend

Requires Node.js 20.9 or newer and npm.

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The frontend uses TypeScript, the App Router, and ESLint.

## Backend

Requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```sh
cd backend
uv sync
uv run fastapi dev main.py
```

Open http://localhost:8000/docs for the API documentation. The app starts with no custom routes.
