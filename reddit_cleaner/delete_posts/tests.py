import logging
import time
from unittest import mock

from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from . import reddit_ops
from .fake_reddit import FakeItem, _Sub, make_account
from .models import CleanupJob


class RunCleanupTests(TestCase):
    def test_deletes_everything_and_overwrites_editable(self):
        acct = make_account(n_posts=6, n_comments=9)
        job = CleanupJob.objects.create(options={"delete_submissions": True, "delete_comments": True, "overwrite_first": True})
        reddit_ops.run_cleanup(acct, job)
        job.refresh_from_db()
        self.assertEqual(job.status, CleanupJob.DONE)
        self.assertEqual((job.submissions_deleted, job.comments_deleted), (6, 9))
        self.assertEqual(job.reddit_username, "demo_user")
        posts = acct.user_obj.submissions._items
        self.assertTrue(all(p.deleted for p in posts))
        # self-posts get overwritten first, link posts don't
        self.assertTrue(all((p.edited_to is not None) == p.is_self for p in posts))
        self.assertTrue(all(c.edited_to for c in acct.user_obj.comments._items))
        # listings overlap (new/top/controversial) but each item counted once
        self.assertEqual(job.submissions_seen, 6)

    def test_filters_keep_days_and_subreddits(self):
        acct = make_account(n_posts=4, n_comments=4)
        job = CleanupJob.objects.create(options={
            "delete_submissions": True, "delete_comments": True,
            "keep_days": 45, "skip_subreddits": ["python"], "overwrite_first": False,
        })
        reddit_ops.run_cleanup(acct, job)
        job.refresh_from_db()
        # posts: i=0 (0d, kept: new), i=1 (30d kept), i=2 (60d, r/Python kept), i=3 (90d deleted)
        self.assertEqual(job.submissions_deleted, 1)
        # comments: 0d,7d,14d,21d all within 45 days -> all kept
        self.assertEqual(job.comments_deleted, 0)
        self.assertEqual(job.skipped, 7)
        self.assertTrue(all(c.edited_to is None for c in acct.user_obj.comments._items))

    def test_dry_run_changes_nothing(self):
        acct = make_account(n_posts=3, n_comments=3)
        job = CleanupJob.objects.create(dry_run=True, options={"delete_submissions": True, "delete_comments": True})
        reddit_ops.run_cleanup(acct, job)
        job.refresh_from_db()
        self.assertEqual((job.submissions_deleted, job.comments_deleted), (3, 3))
        self.assertFalse(any(i.deleted for i in acct.user_obj.submissions._items + acct.user_obj.comments._items))

    def test_only_comments(self):
        acct = make_account(n_posts=3, n_comments=2)
        job = CleanupJob.objects.create(options={"delete_submissions": False, "delete_comments": True})
        reddit_ops.run_cleanup(acct, job)
        job.refresh_from_db()
        self.assertEqual((job.submissions_deleted, job.comments_deleted), (0, 2))

    def test_per_item_failure_is_counted_not_fatal(self):
        acct = make_account(n_posts=3, n_comments=0)
        acct.user_obj.submissions._items[1].fail_delete = True
        job = CleanupJob.objects.create(options={"delete_submissions": True, "delete_comments": True})
        reddit_ops.run_cleanup(acct, job)
        job.refresh_from_db()
        self.assertEqual(job.status, CleanupJob.DONE)
        self.assertEqual((job.submissions_deleted, job.errors), (2, 1))

    def test_auth_failure_marks_failed(self):
        acct = make_account()
        acct.user.me = mock.Mock(side_effect=RuntimeError("401 invalid_grant"))
        job = CleanupJob.objects.create(options={})
        reddit_ops.run_cleanup(acct, job)
        job.refresh_from_db()
        self.assertEqual(job.status, CleanupJob.FAILED)
        self.assertIn("invalid_grant", job.error_message)

    def test_preview_counts_without_deleting(self):
        acct = make_account(n_posts=5, n_comments=7)
        out = reddit_ops.preview(acct, {"delete_submissions": True, "delete_comments": True, "skip_subreddits": ["nyc"]})
        self.assertEqual(out["username"], "demo_user")
        self.assertEqual(out["submissions"] + out["comments"] + out["skipped"], 12)
        self.assertEqual(out["skipped"], 1 + 2)  # p1 in nyc; c1,c5 in nyc
        self.assertFalse(any(i.deleted for i in acct.user_obj.submissions._items))
        self.assertTrue(out["sample"])


class BackgroundTests(TransactionTestCase):
    def test_cancel_stops_early(self):
        acct = make_account(n_posts=50, n_comments=0, delay=0.02)
        job = CleanupJob.objects.create(options={"delete_submissions": True, "delete_comments": False})
        t = reddit_ops.start_in_background(acct, job)
        time.sleep(0.15)
        CleanupJob.objects.filter(id=job.id).update(cancel_requested=True)
        t.join(5)
        job.refresh_from_db()
        self.assertEqual(job.status, CleanupJob.CANCELLED)
        self.assertLess(job.submissions_deleted, 50)
        self.assertGreater(job.submissions_deleted, 0)


FAKE = dict(REDDIT_FAKE=True, REDDIT_OAUTH_ENABLED=True, REDDIT_ALLOW_PASSWORD_LOGIN=False,
            REDDIT_OAUTH_REDIRECT_URI="http://testserver/delete/callback/")


@override_settings(**FAKE)
class OAuthFlowTests(TransactionTestCase):
    def setUp(self):
        reddit_ops._FAKE_ACCOUNT = None
        self.c = Client()

    def _login(self):
        r = self.c.get(reverse("oauth_start"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("state=", r["Location"])
        state = self.c.session["oauth_state"]
        r = self.c.get(reverse("oauth_callback"), {"state": state, "code": "fake-code"})
        self.assertRedirects(r, reverse("index"))
        self.assertEqual(self.c.session["reddit_username"], "demo_user")

    def test_index_renders_signin(self):
        r = self.c.get(reverse("index"))
        self.assertContains(r, "Sign in with Reddit")
        self.assertNotContains(r, "Reddit password")  # legacy form hidden
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", r["Content-Security-Policy"])

    def test_root_redirects(self):
        self.assertRedirects(self.c.get("/"), reverse("index"), fetch_redirect_response=False)

    def test_callback_rejects_bad_state(self):
        self.c.get(reverse("oauth_start"))
        r = self.c.get(reverse("oauth_callback"), {"state": "nope", "code": "fake-code"}, follow=True)
        self.assertContains(r, "state mismatch")
        self.assertNotIn("reddit_refresh_token", self.c.session)

    def test_login_preview_start_status_cancel_logout(self):
        self._login()
        r = self.c.get(reverse("index"))
        self.assertContains(r, "Signed in as u/demo_user")
        # preview
        r = self.c.post(reverse("preview"), {"delete_submissions": "on", "delete_comments": "on"})
        self.assertContains(r, "Dry run for u/demo_user")
        self.assertContains(r, "<b>12</b>")
        # start without confirm -> error
        r = self.c.post(reverse("start"), {"delete_submissions": "on", "mode": "delete"})
        self.assertContains(r, "Tick the confirmation box")
        self.assertEqual(CleanupJob.objects.count(), 0)
        # start dry run (no confirm needed)
        r = self.c.post(reverse("start"), {"delete_submissions": "on", "delete_comments": "on", "mode": "dry_run"})
        job = CleanupJob.objects.get()
        self.assertRedirects(r, reverse("job", kwargs={"job_id": job.id}))
        self.assertTrue(job.dry_run)
        for _ in range(50):
            job.refresh_from_db()
            if job.status == CleanupJob.DONE:
                break
            time.sleep(0.1)
        self.assertEqual(job.status, CleanupJob.DONE, job.error_message)
        r = self.c.get(reverse("job_status", kwargs={"job_id": job.id}))
        self.assertEqual(r.json()["submissions_deleted"], 12)
        self.assertTrue(r.json()["finished"])
        r = self.c.get(reverse("job", kwargs={"job_id": job.id}))
        self.assertContains(r, "Dry run for u/demo_user")
        # another session cannot see the job
        other = Client()
        self.assertEqual(other.get(reverse("job_status", kwargs={"job_id": job.id})).status_code, 404)
        # real delete with confirm
        r = self.c.post(reverse("start"), {"delete_submissions": "on", "delete_comments": "on", "confirm": "on", "mode": "delete"})
        job2 = CleanupJob.objects.exclude(id=job.id).get()
        self.assertFalse(job2.dry_run)
        self.c.post(reverse("job_cancel", kwargs={"job_id": job2.id}))
        for _ in range(50):
            job2.refresh_from_db()
            if job2.status in {CleanupJob.DONE, CleanupJob.CANCELLED}:
                break
            time.sleep(0.1)
        self.assertIn(job2.status, {CleanupJob.DONE, CleanupJob.CANCELLED})
        # logout revokes and clears
        r = self.c.post(reverse("logout"), follow=True)
        self.assertContains(r, "token was revoked")
        self.assertNotIn("reddit_refresh_token", self.c.session)
        self.assertTrue(reddit_ops._fake().revoked)

    def test_start_requires_login(self):
        r = self.c.post(reverse("start"), {"delete_submissions": "on", "mode": "dry_run"}, follow=True)
        self.assertContains(r, "Sign in with Reddit first")

    @override_settings(RATE_LIMIT_MAX=2)
    def test_rate_limit(self):
        self._login()
        for _ in range(2):
            self.c.post(reverse("preview"), {"delete_submissions": "on"})
        r = self.c.post(reverse("preview"), {"delete_submissions": "on"})
        self.assertContains(r, "Too many requests")

    def test_legacy_disabled(self):
        self.assertEqual(self.c.post(reverse("legacy"), {}).status_code, 404)

    def test_healthz(self):
        self.assertEqual(self.c.get(reverse("healthz")).json(), {"ok": True})


@override_settings(REDDIT_FAKE=True, REDDIT_OAUTH_ENABLED=False, REDDIT_ALLOW_PASSWORD_LOGIN=True)
class LegacyPathTests(TransactionTestCase):
    def setUp(self):
        reddit_ops._FAKE_ACCOUNT = None
        self.c = Client()

    def test_index_shows_only_legacy_form(self):
        r = self.c.get(reverse("index"))
        self.assertContains(r, "Reddit password")
        self.assertNotContains(r, "Sign in with Reddit")
        self.assertEqual(self.c.get(reverse("oauth_start")).status_code, 404)

    def test_legacy_start_never_logs_secrets(self):
        creds = {"reddit_username": "demo_user", "client_id": "cid123", "client_secret": "SECRET-XYZ",
                 "password": "hunter2-PASS", "delete_submissions": "on", "delete_comments": "on", "mode": "dry_run"}
        with self.assertLogs(level=logging.DEBUG) as logs:
            r = self.c.post(reverse("legacy"), creds)
        job = CleanupJob.objects.get()
        self.assertRedirects(r, reverse("job", kwargs={"job_id": job.id}))
        blob = "\n".join(logs.output)
        self.assertNotIn("hunter2", blob)
        self.assertNotIn("SECRET-XYZ", blob)
        self.assertNotIn("hunter2", str(job.options))

    def test_legacy_requires_confirm_for_real_delete(self):
        r = self.c.post(reverse("legacy"), {"reddit_username": "u", "client_id": "a", "client_secret": "b",
                                            "password": "c", "delete_comments": "on", "mode": "delete"})
        self.assertContains(r, "Tick the confirmation box")
        self.assertEqual(CleanupJob.objects.count(), 0)

    def test_legacy_bad_credentials(self):
        with mock.patch.object(reddit_ops, "client_from_password", side_effect=RuntimeError("401")):
            r = self.c.post(reverse("legacy"), {"reddit_username": "u", "client_id": "a", "client_secret": "b",
                                                "password": "c", "delete_comments": "on", "mode": "dry_run"})
        self.assertContains(r, "rejected those credentials")


class FormTests(TestCase):
    def test_requires_a_target(self):
        from .forms import CleanupOptionsForm
        f = CleanupOptionsForm({"keep_days": "3"})
        self.assertFalse(f.is_valid())
        self.assertIn("at least one", str(f.errors))

    def test_subreddit_normalisation(self):
        from .forms import CleanupOptionsForm
        f = CleanupOptionsForm({"delete_comments": "on", "skip_subreddits": " r/Python, NYC ,, askreddit"})
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.to_options()["skip_subreddits"], ["askreddit", "nyc", "python"])
