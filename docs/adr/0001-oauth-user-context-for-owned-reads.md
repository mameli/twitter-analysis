# OAuth 2.0 user context instead of an app-only Bearer token

The X API is pay-per-use and bills follower/following reads per returned account. Reads of the authenticated user's own data, made through an app owned by that same user, qualify for the "owned reads" rate ($0.001 per account instead of $0.010, as of September 2026). We therefore authenticate with OAuth 2.0 user context (read-only scopes `tweet.read users.read follows.read offline.access`) and keep the refresh token on the backend, even though an app-only Bearer token would be simpler to set up.

## Consequences

- The X developer app must belong to the same account whose Followers are tracked; using someone else's app loses the discount.
- The backend must handle the one-time OAuth login on localhost and refresh the token automatically.
- Switching to a Bearer token would multiply the cost of every Sync by roughly 10.
