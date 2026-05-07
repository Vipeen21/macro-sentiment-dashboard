Big Picture
This is a Django web app for analyzing macroeconomic policy documents with AI and comparing their sentiment against an economic indicator.

End-to-end flow:

Policy document
    ↓
Stored in database
    ↓
AI analyzes sentiment
    ↓
SentimentResult saved
    ↓
Dashboard view collects data
    ↓
dashboard.html visualizes it with Plotly
Project Structure

Macro-Sentiment/
│
├── manage.py
├── db.sqlite3
│
├── macro_sentiment_project/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── macro_sentiment/
│   ├── models.py
│   ├── views.py
│   ├── tasks.py
│   ├── logic.py
│   ├── admin.py
│   ├── apps.py
│   └── migrations/
│
└── templates/
    └── dashboard.html
manage.py
This is the command-line entry point for Django.

You use it for commands like:

python3 manage.py runserver
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py shell
It loads your Django settings and runs project commands.

macro_sentiment_project/settings.py
This is the main configuration file.

It controls:

installed Django apps
database connection
template folder location
timezone
middleware
static files
debug mode
Important changes here:

"macro_sentiment"
was added to INSTALLED_APPS, so Django knows your app exists.

And:

"DIRS": [BASE_DIR / "templates"]
tells Django where to find dashboard.html.

macro_sentiment_project/urls.py
This file maps browser URLs to Python views.

Current important route:

path("", dashboard_view, name="dashboard")
That means:

http://127.0.0.1:8001/
calls:

dashboard_view()
from macro_sentiment/views.py.

macro_sentiment/models.py
This defines your database structure.

There are three main tables.

PolicyDocument

Stores policy text:

title
content
source
published_date
embedding
Example use: RBI policy statement, budget speech, monetary policy document.

SentimentResult

Stores AI analysis for one document:

document
sentiment_score
label
primary_impact
created_at
Example:

Document: Sample RBI Policy
Score: 0.6
Label: Hawkish
Primary impact: Inflation
EconomicIndicator

Stores macroeconomic data:

name
value
unit
timestamp
Example:

Exchange Rate Volatility
4.25
index
2026-05-02
In short, models.py decides what your database tables look like.

macro_sentiment/views.py
This prepares data for the dashboard.

The main function is:

dashboard_view(request)
It does two queries:

Gets average sentiment score by policy document date.
Gets Exchange Rate Volatility values from the economic indicator table.
Then it converts the data into JSON and sends it to the HTML page.

So this file is the bridge between:

database → webpage
templates/dashboard.html
This is the visible dashboard page.

It uses:

HTML + CSS + JavaScript + Plotly
It receives JSON data from views.py, then draws:

line chart for AI sentiment
bar chart for exchange rate volatility
So visually:

Sentiment Score        → line
Exchange Volatility    → bars
If there is no data, it shows an empty state instead of a blank screen.

macro_sentiment/tasks.py
This is for background AI processing using Celery.

The main function:

process_new_document(doc_id)
Workflow:

Take document ID
    ↓
Fetch PolicyDocument from database
    ↓
Send document content to Gemini
    ↓
Ask for JSON sentiment analysis
    ↓
Parse result
    ↓
Save SentimentResult
This file is not required just to show the dashboard. It becomes important when you want automatic AI analysis instead of manually inserting sentiment data.

macro_sentiment/logic.py
This is for RAG/question-answering.

The function:

get_policy_answer(query)
is designed to:

Convert a user question into an embedding.
Search similar documents in a pgvector database.
Retrieve relevant policy text.
Ask Gemini to answer using that context.
This part is for a future feature like:

Ask: "What is RBI's stance on inflation?"
Answer: "Based on recent policy documents..."
So:

tasks.py = AI sentiment extraction
logic.py = AI question-answering over documents
views.py = dashboard data display
db.sqlite3
This is your current local database.

It stores the sample rows we inserted:

PolicyDocument
SentimentResult
EconomicIndicator
For production or real vector search, you would likely move to PostgreSQL with pgvector.

Complete Architecture

Browser
  |
  | opens /
  ↓
macro_sentiment_project/urls.py
  |
  | routes request
  ↓
macro_sentiment/views.py
  |
  | queries data
  ↓
db.sqlite3
  |
  | returns sentiment + indicator data
  ↓
views.py converts data to JSON
  |
  ↓
templates/dashboard.html
  |
  | Plotly renders chart
  ↓
User sees dashboard
AI processing architecture:

New PolicyDocument saved
  |
  ↓
tasks.py Celery task runs
  |
  ↓
Gemini analyzes document
  |
  ↓
SentimentResult saved
  |
  ↓
Dashboard updates from database
Future RAG architecture:

User asks question
  |
  ↓
logic.py
  |
  ↓
Gemini embeddings
  |
  ↓
PGVector similarity search
  |
  ↓
Relevant policy documents
  |
  ↓
Gemini answer
Current Working Version
Right now, your working dashboard uses:

Django + SQLite + Plotly + sample data
The AI and vector search files are prepared, but to fully activate them you still need:

Google/Gemini API key
Celery worker setup
PostgreSQL + pgvector for real vector search
document upload/import pipeline
So the current project is a working dashboard foundation, and the next stage is making document ingestion and AI analysis automatic.