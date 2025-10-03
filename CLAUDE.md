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

#### Recommended: Shell Script (Interactive)
```bash
chmod +x start.sh                    # First time only
./start.sh menu                      # Interactive menu mode (recommended)
./start.sh local                     # Local development (port 5001)
./start.sh nas                       # NAS environment (port 8080, external access)
./start.sh bg                        # Background mode (NAS environment)
./start.sh status                    # Check server status
./start.sh stop                      # Stop background server
./start.sh ip                        # Show IP addresses
./start.sh log                       # View log files with interactive options
```

#### Manual Execution
```bash
python run.py                        # Development server on http://127.0.0.1:5001 (default)
python run_nas.py                    # NAS environment (0.0.0.0:8080)

# Using environment variables
FLASK_ENV=development python run.py  # Development mode (default)
FLASK_ENV=nas python run.py          # NAS mode (external access)
FLASK_ENV=production python run.py   # Production mode
```

### Database Management
```bash
python scripts/init_db.py           # Initialize database with tables and sample data
python scripts/update_all.py        # Update all lottery data to latest round
python scripts/update_rounds.py     # Update missing rounds incrementally
python scripts/migrate.py           # Database migrations
```

### Development Tools
```bash
# Pre-commit hooks for code quality
pre-commit install                   # Install git hooks (first time only)
pre-commit run --all-files          # Run all hooks on existing files
git commit                           # Hooks run automatically on commit

# Testing (if test files exist)
python -m pytest                    # Run tests with pytest
```

### QR Recognition Desktop App
```bash
# Standalone QR code recognition desktop application
cd lotto_qr_app                      # Navigate to QR app directory
pip install -r requirements.txt     # Install QR app dependencies (OpenCV, Tesseract, etc.)
brew install tesseract              # Install Tesseract OCR (macOS)
python main.py                      # Run QR recognition GUI application
```

## Architecture

### Application Structure
- **App Factory Pattern**: `app.create_app()` with instance-relative configuration
- **Blueprint-based Routing**: Main routes in `app/routes.py` with `main_bp` blueprint
- **SQLAlchemy Integration**: Models in `app/models.py` using Flask-SQLAlchemy 3.x
- **Service Layer**: Business logic separated into `app/services/` modules

### Core Models
- `User`: User authentication with Flask-Login integration and account lockout protection
- `Draw`: Lottery round results with numbers (comma-separated), bonus, and draw date
- `WinningShop`: Shop information where winning tickets were sold (ranks 1-2)
- `Purchase`: User lottery purchases with winning result tracking
- `RecommendationSet`: Persistent user recommendation storage
- `PasswordResetToken`: Secure password reset token management
- `Example`: Sample model for testing database functionality

### Services Architecture
- `lotto_fetcher.py`: Web scraping from official lottery JSON API and HTML pages with retry logic
- `updater.py`: Orchestrates data updates with background processing and progress tracking
- `recommender.py`: Number recommendation algorithms (auto and semi-auto modes)
- `analyzer.py`: Statistical analysis for frequency, combinations, and recommendation reasons
- `lottery_checker.py`: Purchase result checking and statistics
- `recommendation_manager.py`: Persistent recommendation management
- `qr_parser.py`: QR code data parsing and validation from lottery tickets

### QR Recognition Desktop Application
- **Standalone Tkinter GUI**: Desktop application in `lotto_qr_app/` directory
- **Multi-modal Recognition**: Combines OCR and QR code scanning for lottery ticket processing
- **API Integration**: Connects with main Flask application via REST API
- **Image Processing**: Advanced preprocessing for optimal OCR accuracy
- **Components**:
  - `main.py`: Main GUI application with tabbed interface
  - `qr_processor.py`: QR code detection and parsing logic
  - `image_preprocessor.py`: Image enhancement and preprocessing
  - `api_client.py`: HTTP client for Flask app integration
  - `config.py`: Desktop app configuration and settings

### Key Features
- **User Authentication**: Flask-Login integration with password hashing
- **Background Processing**: Threading-based crawling with progress tracking for web interface
- **Retry Logic**: Robust HTTP request handling with configurable retries using `_with_retries()`
- **SQLite with Instance Path**: Database stored in Flask instance folder at `instance/lotto.db`
- **Multi-environment Config**: Development, NAS, and production configurations in `app/config.py`
- **Port Conflict Resolution**: Automatic port conflict detection and resolution in `run.py`
- **Pagination Support**: 2nd rank shop pagination handling in HTML scraping
- **JSON API Endpoints**: RESTful APIs for draws, shops, recommendations, and crawling progress
- **Desktop QR Integration**: Tkinter-based desktop app for lottery ticket scanning and OCR processing
- **Multi-modal Data Input**: Support for both manual entry and automated ticket scanning

### Data Sources and Scraping Strategy
- Official Korean lottery JSON API (`dhlottery.co.kr/common.do`) for draw results
- HTML scraping for winning shop locations with pagination support for 2nd rank shops
- Exponential + binary search algorithm to detect latest available round
- Automatic handling of both single round updates and batch range updates

### Configuration Classes
- `DevelopmentConfig`: Local development (127.0.0.1:5001, DEBUG=True)
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
- Failed login attempt tracking with account locking (5 attempts = 15 min lockout)
- Admin user management system with role-based access
- User-specific purchase tracking and recommendation management
- Session-based authentication with Korean language support

### Port Conflict Resolution System
The application includes intelligent port conflict detection and resolution:
- Automatic detection of port conflicts using `lsof` (macOS) and `fuser` (Linux)
- Special handling for macOS AirPlay service conflicts on port 5000
- Automatic port reallocation when conflicts cannot be resolved
- Process termination capabilities for conflicting services

## Development Guidelines

### Code Architecture Patterns
- **App Factory Pattern**: All Flask apps use `create_app()` factory in `app/__init__.py`
- **Blueprint Organization**: Main routes in `app/routes.py` using `main_bp` blueprint
- **Service Layer Separation**: Business logic isolated in `app/services/` modules
- **Instance-relative Configuration**: Database and sensitive files stored in Flask instance folder
- **Retry Pattern**: All external HTTP requests use `_with_retries()` wrapper for robustness

### Database Patterns
- **SQLAlchemy 3.x Modern Syntax**: Uses current declarative patterns, avoid legacy session usage
- **SQLite WAL Mode**: Configured for concurrent access optimization
- **Migration Scripts**: Database schema changes handled via `scripts/migrate.py`
- **Instance Folder**: Database stored at `instance/lotto.db` for deployment flexibility

### Error Handling & Robustness
- **Retry Logic**: External API calls wrapped with exponential backoff and retry mechanisms
- **Port Conflict Resolution**: Automatic detection and resolution of port conflicts in `run.py`
- **Background Process Management**: PID file-based process tracking for background execution
- **Thread-safe Progress Tracking**: Concurrent operations with real-time status updates
- **Pre-commit Hooks**: Automated code quality checks for large files, trailing whitespace, and end-of-file formatting

### Security Implementation
- **CSRF Protection**: Flask-WTF CSRF tokens on all forms
- **Password Security**: Werkzeug password hashing with strength validation
- **Session Security**: HttpOnly, SameSite cookie configuration
- **Account Lockout**: Failed login attempt tracking with time-based lockout (5 attempts = 15 min lockout)
- **Admin Role Management**: Role-based access control with admin-only endpoints
- **Password Reset**: Secure token-based password reset system with `PasswordResetToken` model

### Mobile-First Development Guidelines

#### **MANDATORY: Mobile Compatibility for All New Features**
When adding any new functionality to this project, you MUST implement mobile versions alongside desktop versions. This is not optional.

#### **Mobile Development Checklist**
For every new page or feature, ensure the following:

**1. Auto-Detection & Redirect**
- Add `mobile_redirect_check()` to main route functions
- Redirect mobile users to dedicated mobile routes
- Example:
```python
@main_bp.get("/new-feature")
@login_required
def new_feature():
    # REQUIRED: Add mobile redirect
    if mobile_redirect_check():
        return redirect(url_for('main.mobile_new_feature'))
    # ... desktop implementation
```

**2. Mobile Route Implementation**
- Create corresponding mobile route: `/mobile/new-feature`
- Mobile routes should be simpler and touch-optimized
- Example:
```python
@main_bp.get("/mobile/new-feature")
@login_required
def mobile_new_feature():
    # Mobile-specific implementation
    return render_template("mobile/new_feature.html", ...)
```

**3. Mobile Template Creation**
- Create mobile template in `app/templates/mobile/`
- Extend `mobile/base.html`
- Follow mobile design patterns:
  - Card-based layout
  - Large touch targets (minimum 44px)
  - Simplified navigation
  - Limited data per screen
  - Touch-friendly interactions

**4. Mobile Design Standards**
- **Layout**: Use `mobile-card` components for content sections
- **Colors**: Follow established gradient themes
- **Typography**: Readable font sizes (minimum 16px)
- **Spacing**: Adequate touch margins (minimum 0.5rem between elements)
- **Actions**: Large buttons with clear labels
- **Navigation**: Bottom-aligned or prominent top navigation

**5. Feature Parity Requirements**
- Core functionality must be available on both desktop and mobile
- Mobile versions can be simplified but not missing key features
- All user interactions must work on touch devices
- Forms should be mobile-optimized with appropriate input types

**6. Testing Requirements**
- Test on actual mobile devices, not just browser dev tools
- Verify touch interactions work correctly
- Ensure responsive behavior across different screen sizes
- Check performance on slower mobile connections

#### **Mobile Template Structure**
```html
{% extends "mobile/base.html" %}
{% block title %}Mobile Page Title{% endblock %}
{% block content %}
<div class="mobile-header">
  <div class="title">
    <h1>🎯 Page Title</h1>
    <div class="subtitle">Page description</div>
  </div>
</div>

<div class="mobile-card">
  <!-- Content goes here -->
</div>

<!-- Desktop version link -->
<div class="desktop-link">
  <a href="{{ url_for('main.feature_name') }}?desktop=1" class="link-desktop">
    🖥️ 데스크톱 버전으로 보기
  </a>
</div>
{% endblock %}
```

#### **Existing Mobile Pages Reference**
- **Dashboard**: `/mobile` - Main overview with real-time updates
- **Strategy**: `/mobile/strategy` - AI recommendations and purchase stats
- **Purchases**: `/mobile/purchases` - Purchase management with mobile-optimized forms
- **Info**: `/mobile/info` - Data browsing with search functionality
- **Crawling**: `/mobile/crawling` - Data collection with progress tracking

#### **Mobile-First Development Process**
1. **Plan**: Design mobile experience first, then desktop
2. **Implement**: Create mobile templates and routes simultaneously with desktop
3. **Test**: Verify functionality on mobile devices
4. **Deploy**: Ensure both versions work in production

#### **Enforcement**
- **All pull requests** must include mobile implementations
- **No new user-facing features** should be merged without mobile support
- **Code reviews** must verify mobile compatibility
- **This is a hard requirement** - not a suggestion

**Remember: Mobile users represent a significant portion of lottery players. Providing an excellent mobile experience is critical for user adoption and satisfaction.**

### API Response Patterns
The application uses consistent JSON response patterns for mobile and AJAX requests:
- **Success**: `{"success": true, "data": {...}, "message": "..."}`
- **Error**: `{"success": false, "error": "...", "details": {...}}`
- **Progress**: `/api/crawling-progress` returns real-time status with `is_running`, `status`, `current_round`, `total_rounds`
- **CSRF Protection**: All POST requests require CSRF tokens, exempt only for specific APIs marked with `@csrf.exempt`

### QR Code Integration Flow
The desktop QR app connects to the Flask backend via REST API:
1. QR app authenticates using `/api/login` endpoint
2. Sends parsed lottery data to `/api/purchases/bulk` endpoint
3. Flask validates and stores purchases in the database
4. Web interface displays QR-collected purchases with `recognition_method='QR'` and `confidence_score`

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
