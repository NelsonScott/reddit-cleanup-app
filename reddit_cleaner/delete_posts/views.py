from django.shortcuts import render
from .forms import DeleteRedditContentForm

# Create your views here.
def delete_reddit_posts(request):
    if request.method == 'post':
        form = DeleteRedditContentForm(request.POST)
        if form.is_valid():
            print(form.cleaned_data['username'])
    else:
        form = DeleteRedditContentForm()

    return render(request, 'delete_posts/index.html', {'form': form})