# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains multiple Flask-based Korean lottery (로또) analysis applications and utilities. The main applications scrape lottery data, analyze winning patterns, and provide recommendations.

### Main Applications

1. **lotto_dashboard/** - Full-featured Flask app with SQLAlchemy, caching, and shop location tracking
2. **lotto_app/** - Flask app with migration support and advanced analysis features
3. **simple_lotto/** - Minimal Flask implementation for basic lottery data
4. **flask_starter/** - Generic Flask starter template
5. **lotto/** - Legacy scripts and utilities

## Common Development Commands

### Virtual Environment Setup
```bash
# For any project directory
make install          # Creates venv and installs dependencies
# OR manually:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running Applications

**lotto_dashboard:**
```bash
cd lotto_dashboard
python app.py                           # Development server on port 8080
./scripts/run_server.sh                 # Interactive menu for fg/bg execution
./scripts/run_server.sh foreground      # Direct foreground execution
./scripts/run_server.sh background      # Background with logging
./scripts/run_server.sh status          # Check running status
./scripts/run_server.sh stop            # Stop all processes
```

**simple_lotto:**
```bash
cd simple_lotto
./run.sh start|stop|restart|status|logs  # Process management
```

**flask_starter:**
```bash
cd flask_starter
python run.py                            # Development server on port 5000
```

### Data Management

**Initialize databases:**
```bash
python scripts/init_db.py              # Create tables and initial data
```

**Update lottery data:**
```bash
python scripts/update_data.py --fetch-all     # Full data fetch
python scripts/update_data.py                 # Incremental update
```

**Update shop locations:**
```bash
python scripts/fetch_shops_override.py        # Fetch winning shop locations
```

### Development Tools

**Code formatting and linting (where available):**
```bash
black .                # Code formatting
ruff check .           # Linting
pytest                 # Run tests
```

## Architecture Notes

### Database Design
- Primary model: `Draw` (lottery round results) with n1-n6 + bonus number
- Secondary models: `Shop` (winning locations), `Recommendation` (analysis results)
- SQLite with WAL mode for concurrency
- Flask-SQLAlchemy 3.0+ with modern declarative syntax

### Web Scraping Architecture
- `scraper.py` modules handle lottery data fetching from official sources
- `requests-cache` for HTTP caching to avoid excessive requests
- BeautifulSoup for HTML parsing
- Robust error handling with retry mechanisms

### Flask Application Structure
```
app/
├── __init__.py          # App factory with blueprint registration
├── config.py           # Configuration management
├── extensions.py       # SQLAlchemy, cache initialization
├── models.py          # Database models
├── routes/            # Blueprint modules (dashboard, api, shops)
├── utils/             # Business logic (scraper, analysis, recommendations)
└── templates/         # Jinja2 templates
```

### Key Features
- Blueprint-based routing for modular organization
- SQLAlchemy event listeners for SQLite optimization
- Flask-Caching for performance optimization
- Instance-relative configuration for deployment flexibility
- Process management scripts with PID tracking

### Data Sources
- Korean lottery official website scraping
- Shop location data from winning retailers
- Analysis algorithms for number frequency and patterns

## Development Guidelines

- Use app factory pattern for Flask applications
- Implement proper error handling with retry logic for web scraping
- Follow SQLAlchemy 2.0+ modern patterns (no legacy session usage)
- Use blueprint organization for larger applications
- Implement proper database connection management with WAL mode
- Use `requests-cache` for external API calls to avoid rate limiting

### Mobile-First Development (MANDATORY)
- **ALL new user-facing features MUST include mobile implementations**
- Add `mobile_redirect_check()` to all new route functions
- Create corresponding `/mobile/*` routes and templates
- Follow mobile design patterns: card-based layout, large touch targets
- Test on actual mobile devices, not just browser dev tools
- See individual project CLAUDE.md files for detailed mobile guidelines
