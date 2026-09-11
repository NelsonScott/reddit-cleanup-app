from django import forms


class CleanupOptionsForm(forms.Form):
    """What to delete. Shared by the OAuth and legacy paths."""

    delete_submissions = forms.BooleanField(label="Delete posts", required=False, initial=True)
    delete_comments = forms.BooleanField(label="Delete comments", required=False, initial=True)
    keep_days = forms.IntegerField(
        label="Keep anything newer than (days)", required=False, min_value=0, max_value=36500,
        help_text="Leave blank to delete everything regardless of age.",
    )
    skip_subreddits = forms.CharField(
        label="Skip these subreddits", required=False, max_length=500,
        help_text="Comma-separated, e.g. AskHistorians, personalfinance",
    )
    overwrite_first = forms.BooleanField(
        label="Overwrite text before deleting", required=False, initial=True,
        help_text="Edits each post/comment to a placeholder first so archives that re-crawl see nothing.",
    )
    confirm = forms.BooleanField(label="I understand this cannot be undone", required=False)

    def clean(self):
        data = super().clean()
        if not data.get("delete_submissions") and not data.get("delete_comments"):
            raise forms.ValidationError("Pick at least one of posts or comments.")
        return data

    def clean_skip_subreddits(self):
        raw = self.cleaned_data.get("skip_subreddits") or ""
        names = {s.strip().lstrip("r/").lower() for s in raw.split(",")}
        return sorted(n for n in names if n)

    def to_options(self):
        d = self.cleaned_data
        return {
            "delete_submissions": bool(d.get("delete_submissions")),
            "delete_comments": bool(d.get("delete_comments")),
            "keep_days": d.get("keep_days"),
            "skip_subreddits": d.get("skip_subreddits") or [],
            "overwrite_first": bool(d.get("overwrite_first")),
        }


class ScriptAppCredentialsForm(CleanupOptionsForm):
    """Legacy path: the user brings their own Reddit 'script' app credentials.

    Only offered when REDDIT_CLEANER_ALLOW_PASSWORD is on. Nothing here is
    persisted; values are used once to build a PRAW client and then dropped.
    """

    reddit_username = forms.CharField(label="Reddit username", max_length=64)
    client_id = forms.CharField(label="Client ID", max_length=100)
    client_secret = forms.CharField(label="Client secret", max_length=100, widget=forms.PasswordInput(render_value=False))
    password = forms.CharField(label="Reddit password", max_length=200, widget=forms.PasswordInput(render_value=False))
    field_order = ["reddit_username", "client_id", "client_secret", "password"]
