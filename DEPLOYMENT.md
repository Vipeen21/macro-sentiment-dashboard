# Deployment

## Render

1. Push this project to GitHub.
2. In Render, create a new Blueprint from the repository.
3. Add the `GOOGLE_API_KEY` environment variable in Render.
4. Deploy.

Render will run:

```bash
./build.sh
gunicorn macro_sentiment_project.wsgi:application
```

## Required Environment Variables

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<generated secret>
DJANGO_ALLOWED_HOSTS=<your-domain>,localhost,127.0.0.1
GOOGLE_API_KEY=<your Gemini API key>
GOOGLE_GENAI_CHAT_MODEL=gemini-2.5-flash
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SECURE_HSTS_SECONDS=31536000
```
