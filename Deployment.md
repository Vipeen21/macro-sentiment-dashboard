# Deployment

## Render

1. Push this project to GitHub.
2. In Render, create a new Blueprint from the repository.
3. Add the optional `GOOGLE_API_KEY` environment variable in Render if you want Gemini-powered sentiment and answers.
4. Deploy.

Render will run:

```bash
./build.sh
gunicorn macro_sentiment_project.wsgi:application
```

The build seeds historical MPC data, attempts to ingest the latest RBI policy document, and attempts to fetch live USD-INR volatility. Live RBI refresh also runs on dashboard requests by default.

## Required Environment Variables

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<generated secret>
DJANGO_ALLOWED_HOSTS=<your-domain>,localhost,127.0.0.1
GOOGLE_API_KEY=<your Gemini API key>
GOOGLE_GENAI_CHAT_MODEL=gemini-2.5-flash
RBI_REFRESH_ON_REQUEST=True
RBI_POLICY_URL=<optional explicit RBI policy URL>
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SECURE_HSTS_SECONDS=31536000
```
