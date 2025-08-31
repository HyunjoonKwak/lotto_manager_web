# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask starter template for Korean lottery (로또) analysis applications. It provides a foundation for building lottery data scraping, analysis, and recommendation services with user authentication and a web interface.

## Common Development Commands

### Environment Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Running the Application
```bash
python run.py                    # Development server on http://127.0.0.1:5000
python run_local.py              # Explicit local development (port 5000)
python run_nas.py                # NAS environment (0.0.0.0:8080)

# Using environment variables
FLASK_ENV=development python run.py  # Development mode
FLASK_ENV=nas python run.py          # NAS mode (external access)
FLASK_ENV=production python run.py   # Production mode
```

### Database Management
```bash
python scripts/init_db.py       # Initialize database with tables and sample data
python scripts/update_all.py    # Update all lottery data to latest round
python scripts/update_rounds.py # Update missing rounds incrementally
python scripts/migrate.py       # Database migrations
```

## Architecture

### Application Structure
- **App Factory Pattern**: `app.create_app()` with instance-relative configuration
- **Blueprint-based Routing**: Main routes in `app/routes.py` with `main_bp` blueprint
- **SQLAlchemy Integration**: Models in `app/models.py` using Flask-SQLAlchemy 3.x
- **Service Layer**: Business logic separated into `app/services/` modules

### Core Models
- `User`: User authentication with Flask-Login integration
- `Draw`: Lottery round results with numbers (comma-separated), bonus, and draw date
- `WinningShop`: Shop information where winning tickets were sold (ranks 1-2)
- `Purchase`: User lottery purchases with winning result tracking
- `RecommendationSet`: Persistent user recommendation storage
- `Example`: Sample model for testing database functionality

### Services Architecture
- `lotto_fetcher.py`: Web scraping from official lottery JSON API and HTML pages with retry logic
- `updater.py`: Orchestrates data updates with background processing and progress tracking
- `recommender.py`: Number recommendation algorithms (auto and semi-auto modes)
- `analyzer.py`: Statistical analysis for frequency, combinations, and recommendation reasons
- `lottery_checker.py`: Purchase result checking and statistics
- `recommendation_manager.py`: Persistent recommendation management

### Key Features
- **User Authentication**: Flask-Login integration with password hashing
- **Background Processing**: Threading-based crawling with progress tracking for web interface
- **Retry Logic**: Robust HTTP request handling with configurable retries using `_with_retries()`
- **SQLite with Instance Path**: Database stored in Flask instance folder at `instance/lotto.db`
- **Multi-environment Config**: Development, NAS, and production configurations in `app/config.py`
- **Port Conflict Resolution**: Automatic port conflict detection and resolution in `run.py`
- **Pagination Support**: 2nd rank shop pagination handling in HTML scraping
- **JSON API Endpoints**: RESTful APIs for draws, shops, recommendations, and crawling progress

### Data Sources and Scraping Strategy
- Official Korean lottery JSON API (`dhlottery.co.kr/common.do`) for draw results
- HTML scraping for winning shop locations with pagination support for 2nd rank shops
- Exponential + binary search algorithm to detect latest available round
- Automatic handling of both single round updates and batch range updates

### Configuration Classes
- `DevelopmentConfig`: Local development (127.0.0.1:5000, DEBUG=True)
- `NASConfig`: External access allowed (0.0.0.0:8080, DEBUG=True)
- `ProductionConfig`: Production deployment (0.0.0.0:8080, DEBUG=False)

### Progress Tracking System
The application includes a sophisticated background crawling system with real-time progress updates:
- Thread-safe progress tracking with status, current/total rounds, elapsed time
- Multiple operation types: single round, range update, missing rounds, full crawling
- Web interface shows real-time progress via `/api/crawling-progress` endpoint

### Authentication System
- User registration and login with Flask-Login
- Password hashing using Werkzeug security
- User-specific purchase tracking and recommendation management
- Session-based authentication with Korean language support
