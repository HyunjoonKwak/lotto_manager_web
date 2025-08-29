# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask starter template for Korean lottery (로또) analysis applications. It provides a foundation for building lottery data scraping, analysis, and recommendation services with a web interface.

## Common Development Commands

### Environment Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Running the Application
```bash
python run.py                    # Development server on http://127.0.0.1:5000
```

### Database Management
```bash
python scripts/init_db.py       # Initialize database with tables and sample data
python scripts/update_all.py    # Update all lottery data to latest round
python scripts/update_rounds.py # Update missing rounds incrementally
```

## Architecture

### Application Structure
- **App Factory Pattern**: `app.create_app()` with instance-relative configuration
- **Blueprint-based Routing**: Main routes in `app/routes.py` with `main_bp` blueprint
- **SQLAlchemy Integration**: Models in `app/models.py` using Flask-SQLAlchemy 3.x
- **Service Layer**: Business logic separated into `app/services/` modules

### Core Models
- `Draw`: Lottery round results with numbers, bonus, and draw date
- `WinningShop`: Shop information where winning tickets were sold (ranks 1-2)
- `Example`: Sample model for testing database functionality

### Services Architecture
- `lotto_fetcher.py`: Web scraping from official lottery API and HTML pages
- `updater.py`: Orchestrates data updates with error handling and progress tracking
- `recommender.py`: Number recommendation algorithms (auto and semi-auto modes)

### Key Features
- **Retry Logic**: Robust HTTP request handling with configurable retries
- **SQLite with Instance Path**: Database stored in Flask instance folder
- **JSON API Endpoints**: RESTful APIs for draws, shops, and recommendations
- **Web Interface**: Template-based UI for lottery data visualization

### Data Sources
- Official Korean lottery JSON API for draw results
- HTML scraping for winning shop locations and details
- Automatic detection of latest available round

### Configuration
- Development config with SQLite database in instance folder
- Production-ready configuration classes in `app/config.py`
- Environment-based secret key override support
