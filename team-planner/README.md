# Team Planner - deploy to Vercel

A static site (no build step) plus one serverless function, `api/progress.js`.

## Deploy (about 2 minutes)
1. Push this `team-planner` folder to a GitHub repo (or run `npx vercel` inside it).
2. In Vercel: **Add New -> Project**, import the repo. Framework preset: **Other**. No build command, no output directory.
3. Deploy. Sign in with your first name in lowercase and the team password `123456`
   (yashwanth, yash, janavi, aparna, karthik).

## Make progress shared across the team
Without a store, ticks are saved only in each person's browser (the site shows a yellow note).
To share them:
1. In the Vercel project: **Storage -> Create / Connect -> Upstash for Redis** (Marketplace, free tier is enough).
2. Connect it to this project. Vercel adds `KV_REST_API_URL` and `KV_REST_API_TOKEN`
   (`UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` also work).
3. **Redeploy**. The yellow note disappears and everyone sees the same progress, refreshed every 15 s.

Only the owner of a file can tick it - the function checks the username, the team password and the
file's owner before saving.

## What is inside
- `index.html`, `assets/styles.css`, `assets/app.js` - the site (Archivo font, no framework).
- `assets/plan.js` - the generated plan: people, 5 days, all 52 files with their code, explanations,
  push commands and review demos.
- `api/progress.js` - GET returns every tick; POST saves one tick.
- `vercel.json` - clean URLs and no stale caching of the plan.
