# Deploying hosted mode on Vercel and Neon

Hosted mode (R-50 to R-56) runs CodeCompass as a website: people sign in with GitHub, Google, or a username and password, and each account keeps its own data. It runs on Vercel's free plan, with its data in a free Neon PostgreSQL database. Local mode is unaffected: `flask --app codecompass run` on a laptop works as before, offline.

Nothing here is automatic. Each step is done once, by hand, in the services' own websites.

## What you need

- A GitHub account, for the code and for registering the sign-in app
- A Google account, for registering Google sign-in (optional)
- A Vercel account (free plan), signed up with GitHub
- A Neon account (free plan)
- This repository pushed to GitHub

## 1. Make the database (Neon)

1. In Neon, create a project. Pick the region nearest your users, and remember it: Vercel's functions should run in the same region (step 4).
2. On the project's dashboard, open **Connect**, turn **Connection pooling off**, and copy the connection string. It looks like `postgresql://user:password@ep-....region.aws.neon.tech/neondb?sslmode=require`. Change `sslmode=require` to `sslmode=verify-full`, so the app also checks that it is talking to Neon (security review), not only that the connection is encrypted.

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

## 2b. Register Google sign-in (optional)

Skip this to offer only GitHub and username sign-in; the Google button shows only once its client ID is set.

1. In the [Google Cloud console](https://console.cloud.google.com/), create a project (or pick one).
2. Open **APIs & Services > OAuth consent screen** (now called **Google Auth Platform**). Choose **External**, give the app name CodeCompass and a support email, and add only the scopes `openid` and `.../auth/userinfo.profile`. Under **Audience**, publish the app, so any Google account can sign in, not only listed test users. With only these basic scopes, Google does not need to verify the app.
3. Open **Clients > Create client**, choose **Web application**, and under **Authorized redirect URIs** add your Vercel address followed by `/signin/google/callback`.
4. Create it, and copy the **Client ID** and **Client secret**.

CodeCompass asks Google for the account's ID and name only: no email, and nothing else in the account.

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

1. In Vercel, **Add New > Project**, and import the repository. Vercel reads `vercel.json`, which sends every request to `api/index.py`, and `.python-version`, which sets Python 3.14 to match the tests in CI. Without it, Vercel would use its default, Python 3.12.
2. Under **Environment Variables**, add:

   | Name | Value |
   | --- | --- |
   | `CODECOMPASS_MODE` | `hosted` |
   | `CODECOMPASS_DATABASE_URL` | the Neon connection string |
   | `CODECOMPASS_SECRET_KEY` | a long random string; make one with `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `CODECOMPASS_GITHUB_CLIENT_ID` | the OAuth app's client ID |
   | `CODECOMPASS_GITHUB_CLIENT_SECRET` | the OAuth app's client secret |
   | `CODECOMPASS_GOOGLE_CLIENT_ID` | the Google client's ID (optional, step 2b) |
   | `CODECOMPASS_GOOGLE_CLIENT_SECRET` | the Google client's secret (optional, step 2b) |

   Never commit these to the repository.
3. Under **Settings > Functions**, set the function region to Neon's region.
4. Deploy. Open the address, sign in with GitHub (and Google, if set up), and check that the dashboard opens.
5. If the address differs from what you gave GitHub in step 2 or Google in step 2b, update the callback URLs to match.

Changing the secret key signs everyone out. Changing the database string points the site at another database.

## Limits to know

- **Accounts:** at most 50 can sign up (`MAX_ACCOUNTS` in `core/constants.py`); after that, new accounts are refused and existing ones still sign in. Free plans have usage limits, so watch Vercel's and Neon's usage pages as testers join.
- **Sync:** Codeforces and AtCoder only; LeetCode stays in local mode (R-33). A sync runs in steps of up to 8 seconds while any CodeCompass page of that account is open, and pauses when they are all closed (R-54). Requests to each site are spaced across every account, so syncs wait their turn when several run at once.
- **Uploads:** Vercel refuses requests over about 4.5 MB. Backups from either mode hold only the problems their records use, and the restore form compresses them with gzip before sending, so they are far under the limit. A backup saved by an older local version holds the whole catalog, about 4 MB, but compressed it is about 1 MB.
- **First visit after a pause:** Neon pauses an idle database, so the first page after a quiet spell takes a few seconds longer.
- **Vercel's free plan** is for non-commercial use.

## Seeing and removing accounts

From the laptop, with the same three environment variables as in step 3:

```
flask --app codecompass accounts
flask --app codecompass accounts delete <name>
flask --app codecompass accounts reset-password <username>
```

The first lists every account with its id, when it was made, when it last signed in, how many attempts it has, and how it signs in (github, google, or password). The second deletes one, after asking, by its GitHub username, Google name, or username. Use it if throwaway accounts fill the 50-account cap. Each way of signing in is its own account, so two can share a name; then add `--method github`, `--method google`, or `--method password` to say which. Google accounts are named by their Google name, so two of them can share one too; then add `--id` with the id from the list.

The third is for someone who signs in with a username and forgot the password. The site sends no email, so it cannot send a reset link. The command prints a new random password and signs the account out everywhere. Check that the request really comes from the account's owner (for example, someone who told you the username when they signed up), pass the password on privately, and ask them to change it on their account page. The site itself has no admin page.

## Moving data between local mode and an account (R-55)

- **Local to hosted:** in local mode, **Settings > Download backup**. Then on the site, **Settings > Restore from backup** with that file. It replaces the account's data, and can be undone for a day, until you save something new.
- **Hosted to local:** on the site, download a backup the same way, and restore it in local mode.

The two copies are separate; nothing keeps them in step.

## Before inviting testers

R-53's security review is in `docs/verification/security_review.md`. It covers the code, not the live deployment: once deployed, check that the site redirects plain HTTP to HTTPS, that signing in and out works with each way of signing in, and that the environment variables are set only in Vercel.
