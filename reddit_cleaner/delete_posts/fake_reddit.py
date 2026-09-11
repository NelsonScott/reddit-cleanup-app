"""A stand-in for PRAW used by the tests and by demo mode
(REDDIT_CLEANER_FAKE=1). Mimics just enough of praw.Reddit to drive the app:
user.me(), submissions/comments listings, edit(), delete(), auth.url/authorize.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import urlencode


@dataclass
class _Sub:
    display_name: str


@dataclass
class FakeItem:
    id: str
    subreddit: _Sub
    created_utc: float
    title: str = ""
    body: str = ""
    is_self: bool = True
    deleted: bool = False
    edited_to: str | None = None
    fail_delete: bool = False
    delay: float = 0.0

    def edit(self, text):
        self.edited_to = text

    def delete(self):
        if self.delay:
            time.sleep(self.delay)
        if self.fail_delete:
            raise RuntimeError("simulated API failure")
        self.deleted = True


class _Listing:
    """Like Reddit, deleted items drop out of every listing."""

    def __init__(self, items):
        self._items = items

    def _live(self):
        return [i for i in self._items if not i.deleted]

    def new(self, limit=None):
        return iter(sorted(self._live(), key=lambda i: -i.created_utc))

    def top(self, limit=None):
        return iter(self._live())

    def controversial(self, limit=None):
        return iter(self._live())


@dataclass
class FakeUser:
    name: str
    submissions: _Listing
    comments: _Listing


class _UserNS:
    def __init__(self, user):
        self._user = user

    def me(self):
        return self._user


class _Auth:
    def __init__(self, reddit):
        self._reddit = reddit

    def url(self, scopes, state, duration="permanent"):
        # Demo mode: bounce straight back to our own callback.
        return self._reddit.redirect_uri + "?" + urlencode({"state": state, "code": "fake-code"})

    def authorize(self, code):
        assert code == "fake-code"
        return "fake-refresh-token"


@dataclass
class FakeReddit:
    user_obj: FakeUser
    redirect_uri: str = "http://localhost:8000/delete/callback/"
    revoked: bool = False
    auth: _Auth = field(init=False)
    user: _UserNS = field(init=False)

    def __post_init__(self):
        self.auth = _Auth(self)
        self.user = _UserNS(self.user_obj)


def make_account(username="demo_user", n_posts=12, n_comments=30, now=None, delay=0.0) -> FakeReddit:
    now = now or time.time()
    subs = ["AskReddit", "nyc", "Python", "personalfinance"]
    posts = [
        FakeItem(id=f"p{i}", subreddit=_Sub(subs[i % len(subs)]), created_utc=now - i * 86400 * 30,
                 title=f"Post number {i} about {subs[i % len(subs)]}", is_self=(i % 3 != 0), delay=delay)
        for i in range(n_posts)
    ]
    comments = [
        FakeItem(id=f"c{i}", subreddit=_Sub(subs[i % len(subs)]), created_utc=now - i * 86400 * 7,
                 body=f"Comment {i}: something I said in r/{subs[i % len(subs)]}", delay=delay)
        for i in range(n_comments)
    ]
    return FakeReddit(FakeUser(username, _Listing(posts), _Listing(comments)))
