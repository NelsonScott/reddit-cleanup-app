## Reddit Cleaner
https://reddit.scottnelson.xyz/

Simple django app to automate the deletion of your Reddit submissions (posts) and comments. Using the Reddit API via PRAW (Python Reddit API Wrapper), the web app allows you to input your Reddit credentials through a form, and then proceed to delete all of your submissions and comments.

Inspired from [JosemyDuarte's](https://github.com/JosemyDuarte/reddit-cleaner) original script.

## Features
- Delete **all Reddit submissions (posts)** from your account.
- Delete **all Reddit comments** from your account.

## Installation

### Dependencies
- Python 3.x
- Django
- PRAW

### Step 1: Clone the Repository
```bash
git clone https://github.com/NelsonScott/reddit-cleanup-app
```

### Step 2: Set Up Reddit API Credentials
You'll need a reddit 'dev app' - Go here to get your Free [API credentials](https://www.reddit.com/prefs/apps).

### Step 3: Dev Install & Run
```bash
pipenv install
pipenv shell
python manage.py runserver
```
Access in browser
`http://127.0.0.1:8000/delete/`