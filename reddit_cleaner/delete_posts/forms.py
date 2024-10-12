from django import forms

class DeleteRedditContentForm(forms.Form):
    reddit_username = forms.CharField(label='Reddit Username', max_length=100)
    client_id = forms.CharField(label='Client ID', max_length=100)
    client_secret = forms.CharField(label='Client Secret', max_length=100)
    user_agent = forms.CharField(label='User Agent', max_length=100)
    password = forms.CharField(label='Password', widget=forms.PasswordInput())