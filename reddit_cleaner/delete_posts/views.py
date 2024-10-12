import logging
from django.shortcuts import render
from django.contrib import messages
import praw
from .forms import DeleteRedditContentForm

logger = logging.getLogger(__name__)

def delete_reddit_posts(request):
    if request.method == 'POST':
        form = DeleteRedditContentForm(request.POST)
        if form.is_valid():
            try:
                logger.info(f"Processing deletion for user: {form.cleaned_data['reddit_username']}")

                # Fetch submissions using PRAW
                reddit = praw.Reddit(
                    client_id=form.cleaned_data["client_id"],
                    client_secret=form.cleaned_data["client_secret"],
                    user_agent=form.cleaned_data["user_agent"],
                    username=form.cleaned_data["reddit_username"],
                    password=form.cleaned_data["password"]
                )

                user = reddit.user.me()
                logger.info(f"Authenticated Reddit user: {user.name}")

                # Fetch and delete submissions
                submissions = user.submissions.new(limit=None)
                submission_count = 0
                for submission in submissions:
                    submission_count += 1
                    # Uncomment the line below to actually delete
                    submission.delete()
                    logger.info(f"Deleted submission: {submission.title}")

                logger.info(f"Deleted {submission_count} submissions for user: {user.name}")

                # Fetch and delete comments
                comments = user.comments.new(limit=None)
                comment_count = 0
                for comment in comments:
                    comment_count += 1
                    comment.delete()
                    logger.info(f"Deleted comment: {comment.id} - {comment.body[:50]}")  # Logging first 50 characters

                logger.info(f"Deleted {comment_count} comments for user: {user.name}")

                top_comments = user.comments.top(limit=None)
                for comment in top_comments:
                    comment.delete()
                    logger.info(f"Deleted top comment: {comment.id} - {comment.body[:50]}")

                messages.success(request, 'Reddit posts & comments deleted! Note that private messages may need to be deleted manually.')
            except Exception as e:
                logger.error(f"An error occurred during deletion: {str(e)}")
                messages.error(f"An error occurred, please double check credentials")
        else:
            logger.warning("Form validation failed.")
            messages.error(request, 'Form is not valid. Please correct the errors.')
    else:
        logger.info("Rendering form")
        form = DeleteRedditContentForm()

    return render(request, 'delete_posts/index.html', {'form': form})
