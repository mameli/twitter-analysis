# Setting up X API access

One-time steps on the X developer console. Only you can do these; they involve your account and payment details.

1. **Developer account.** Sign in to [console.x.com](https://console.x.com) with the **same X account** whose followers you want to track. The owned-read price only applies when the app belongs to that account (see [ADR 0001](adr/0001-oauth-user-context-for-owned-reads.md)).
2. **Credits and spending limit.** Buy a few dollars of credits and set a **monthly spending limit** (for example $5). This protects you even if the app's own budget check had a bug.
3. **Create an app.** Under *User authentication settings*:
   - App permissions: **Read**
   - Type of App: **Native App** (public client, no secret). If you pick *Web App*, also copy the client secret.
   - Callback URI: `http://127.0.0.1:8000/api/auth/callback`
   - Website URL: any valid URL, for example your X profile.
4. **Copy the OAuth 2.0 Client ID** (and secret, for a Web App) into `backend/.env`, starting from `backend/.env.example`.
5. **Log in.** Start the app (see the README), import the archive, then click *Log in with X* on the dashboard.

Before the first Sync, check the current prices on the console's pricing page. The app assumes $0.001 per account for your own Followers/Followings and $0.010 per account for other user reads. If X has changed them, update `OWNED_READ_USD` and `USER_READ_USD` in `backend/src/twitter_analysis/tracker.py`.
