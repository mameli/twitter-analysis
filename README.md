# Twitter Analysis

Personal localhost dashboard that tracks who follows and unfollows your X account. Vocabulary: [CONTEXT.md](CONTEXT.md).

- `backend/`: FastAPI + SQLite. Every Sync reads your Followers and Followings from the X API, compares them with the previous Snapshot, and records the changes. Each paid call is logged, and a Sync is refused if it could push the month past the budget (default $5).
- `frontend/`: Vite + React + TypeScript.

## Before you start: it costs real money

The X API is pay-per-use, and X prices it like it knows you're curious. Every Sync pays $0.001 for each of your Followers and Followings, plus $0.01 for each Follower who disappeared since the last Sync (the app has to ask X whether they unfollowed you or just got suspended).

In practice:

| Followers + Followings | Cost per Sync |
|---|---|
| 600 | ~$0.90 |
| 10,000 | ~$10 |
| 100,000 | ~$100+ |

So if you have lots of followers, leave it. At that point you can afford to not care who unfollowed you.

Check the current prices on [console.x.com](https://console.x.com) before your first Sync; X changes them now and then.

## First run

1. Request your data archive on X (*Settings → Your account → Download an archive of your data*) and wait for the zip.
2. Follow [docs/setup-x.md](docs/setup-x.md) to create the X app, then `cp backend/.env.example backend/.env` and fill it in.
3. Start both servers:

   ```bash
   cd backend && uv run --env-file .env uvicorn --factory twitter_analysis.main:app_from_env --host 127.0.0.1 --port 8000
   ```

   ```bash
   cd frontend && npm install && npm run dev
   ```

4. Open http://127.0.0.1:5173, import the archive zip by its path, log in with X, then press **Sync** whenever you want an update (see the cost table above).

## Tests

```bash
cd backend && uv run pytest && uv run pyright src
```

```bash
cd frontend && npx tsc -b
```

Tests never call the real X API.

## License

[MIT](LICENSE)
