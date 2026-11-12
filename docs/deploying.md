# Deploying hosted mode on Vercel and Neon

Hosted mode (R-50 to R-56) runs CodeCompass as a website: people sign in with GitHub, and each account keeps its own data. It runs on Vercel's free plan, with its data in a free Neon PostgreSQL database. Local mode is unaffected: `flask --app codecompass run` on a laptop works as before, offline.

Nothing here is automatic. Each step is done once, by hand, in the services' own websites.

## What you need

- A GitHub account, for the code and for registering the sign-in app
- A Vercel account (free plan), signed up with GitHub
- A Neon account (free plan)
- This repository pushed to GitHub

## 1. Make the database (Neon)

1. In Neon, create a project. Pick the region nearest your users, and remember it: Vercel's functions should run in the same region (step 4).
2. On the project's dashboard, open **Connect**, turn **Connection pooling off**, and copy the connection string. It looks like `postgresql://user:password@ep-....region.aws.neon.tech/neondb?sslmode=require`.

   Use the direct connection, not the pooled one: each account's requests set which schema they read (R-52), and the pooler does not keep that setting between queries.
3. Keep the string secret. It is the database password.

## 2. Register the sign-in app (GitHub)

1. In GitHub, open **Settings > Developer settings > OAuth Apps > New OAuth App**.
2. Fill in:
   - **Application name:** CodeCompass
   - **Homepage URL:** your Vercel address, for example `https://codecompass-yourname.vercel.app` (you can change it after the first deploy)
   - **Authorization callback URL:** the same address followed by `/signin/github/callback`
3. Create it, then **Generate a new client secret**. Copy the **Client ID** and the secret.

CodeCompass asks GitHub for the public profile only: no email and no access to repositories.

## 3. Load the catalog once (from your laptop)

The first start loads about 11,000 problems (the catalog and reserve) into the database, which can take longer than a request may run on Vercel's free plan. Load them once from the laptop instead. In PowerShell, in the project folder with the virtual environment active:

```
pip install -r requirements.txt
$env:CODECOMPASS_MODE = "hosted"
$env:CODECOMPASS_DATABASE_URL = "<the Neon connection string>"
$env:CODECOMPASS_SECRET_KEY = "anything"
python -c "from codecompass import create_app; create_app()"
Remove-Item Env:CODECOMPASS_MODE, Env:CODECOMPASS_DATABASE_URL, Env:CODECOMPASS_SECRET_KEY
```

The last line matters: it puts the shell back in local mode, so the next `flask run` uses your local data. Repeat this step after changing the catalog or reserve files; otherwise the first request after deploying does it.

## 4. Deploy (Vercel)

1. In Vercel, **Add New > Project**, and import the repository. Vercel reads `vercel.json`, which sends every request to `api/index.py`.
2. Under **Environment Variables**, add:

   | Name | Value |
   | --- | --- |
   | `CODECOMPASS_MODE` | `hosted` |
   | `CODECOMPASS_DATABASE_URL` | the Neon connection string |
   | `CODECOMPASS_SECRET_KEY` | a long random string; make one with `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `CODECOMPASS_GITHUB_CLIENT_ID` | the OAuth app's client ID |
   | `CODECOMPASS_GITHUB_CLIENT_SECRET` | the OAuth app's client secret |

   Never commit these to the repository.
3. Under **Settings > Functions**, set the function region to Neon's region.
4. Deploy. Open the address, sign in with GitHub, and check that the dashboard opens.
5. If the address differs from what you gave GitHub in step 2, update the OAuth app's homepage and callback URLs to match.

Changing the secret key signs everyone out. Changing the database string points the site at another database.

## Limits to know

- **Accounts:** at most 50 can sign up (`MAX_ACCOUNTS` in `core/constants.py`); after that, new accounts are refused and existing ones still sign in. Free plans have usage limits, so watch Vercel's and Neon's usage pages as testers join.
- **Sync:** Codeforces and AtCoder only; LeetCode stays in local mode (R-33). A sync runs in steps of up to 8 seconds while any CodeCompass page of that account is open, and pauses when they are all closed (R-54). Requests to each site are spaced across every account, so syncs wait their turn when several run at once.
- **Uploads:** Vercel refuses requests over about 4.5 MB. A backup from an account is small; a backup from local mode holds the whole catalog, about 4 MB, so it may be near the limit.
- **First visit after a pause:** Neon pauses an idle database, so the first page after a quiet spell takes a few seconds longer.
- **Vercel's free plan** is for non-commercial use.

## Moving data between local mode and an account (R-55)

- **Local to hosted:** in local mode, **Settings > Download backup**. Then on the site, **Settings > Restore from backup** with that file. It replaces the account's data, and can be undone for a day, until you save something new.
- **Hosted to local:** on the site, download a backup the same way, and restore it in local mode.

The two copies are separate; nothing keeps them in step.

## Before inviting testers

R-53 asks for a security review before anyone but the author signs in: go through sign-in, the per-account separation (R-52), form tokens, limits, and the deployment settings above, and record what was checked and found in `docs/verification/`.
