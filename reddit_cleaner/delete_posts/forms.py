from django import forms

class DeleteRedditContentForm(forms.Form):
    username = forms.CharField(label='Reddit username', max_length=100)