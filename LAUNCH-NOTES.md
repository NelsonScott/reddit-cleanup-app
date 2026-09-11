# Launch notes (drafts — nothing has been posted)

The backlog item said "then actually publicize (ProductHunt, discords)". Below are
ready-to-paste drafts. Post only after the OAuth app is registered and the 2.0 branch is
live at https://reddit.scottnelson.xyz/ — the first thing people will click is "Sign in
with Reddit".

## Product Hunt

**Name:** Reddit Cleaner
**Tagline:** Wipe your Reddit history in one click, with a dry run first
**Description:**
Delete every post and comment on your Reddit account through the official API. Sign in
with Reddit (no password typed into a third-party site), see exactly how many items will
go, keep anything newer than N days or in subreddits you name, and watch a live progress
page while it runs. Text is overwritten before deletion so re-crawled archives get a
placeholder. Open source, self-hostable, nothing stored.
**Topics:** Privacy, Open Source, Productivity
**First comment (maker):**
I built this after realising every "delete your Reddit history" tool either wanted my
password or was a script I had to run myself. This one uses Reddit's OAuth, so the site
never sees your password, revokes its own token when you sign out, and shows you a dry
run before anything is deleted. It's a small Django app; the source is on GitHub if
you'd rather run it yourself. Happy to answer questions on how the deletion works
(Reddit caps history listings at ~1,000 items, which is why there's a second-pass note).

## r/privacy / r/DataHoarder style post

**Title:** I made a free, open-source tool to delete your Reddit history via OAuth (no password, dry run first)
**Body:**
Reddit Cleaner: https://reddit.scottnelson.xyz/ — source: https://github.com/NelsonScott/reddit-cleanup-app

- Sign in with Reddit; the app asks for `identity history edit read` and revokes the token on sign-out
- Dry run shows counts + a sample before you confirm
- Keep recent items (N days) or whole subreddits
- Overwrites text before deleting, so archives that re-crawl get a placeholder
- Runs in the background with a live progress page; big accounts take a while (Reddit's ~60 writes/min)

Known limits: Reddit only returns ~1,000 items per listing, so very old accounts may need a
second pass (the dry run will tell you). PMs and saved items aren't touched.

## Discord blurb (one-liner)
Made a thing: reddit.scottnelson.xyz wipes your Reddit posts/comments via OAuth (no
password), with a dry run and a live progress page. Open source. Feedback welcome.

## Before posting — checklist
- [ ] Reddit "web app" registered, `REDDIT_OAUTH_*` set, `REDDIT_CLEANER_ALLOW_PASSWORD=0`
- [ ] `manage.py check --deploy` clean on the server; HSTS shows up over https
- [ ] Run a dry run + real delete on a throwaway account
- [ ] Tag a `v2.0.0` release on GitHub so the "Source" link matches what's deployed
