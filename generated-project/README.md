# Study Planner

A clean and simple web application built with Flask and SQLite to help students plan, manage, and track their study tasks and subjects.

## Running locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Open your browser and navigate to `http://localhost:8080`.

## Running with Docker

```bash
docker build -t study-planner .
docker run -p 8080:8080 study-planner
```

## Running Tests

```bash
pytest
```
