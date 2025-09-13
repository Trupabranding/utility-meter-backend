# Utility Meter Reading API

A RESTful API for managing utility meter readings, assignments, and approvals. This system is designed to help utility companies manage field agents who collect meter readings, with features for assignment management, reading verification, and approval workflows.

## Features

- **User Management**: Role-based access control (Admin, Manager, Agent)
- **Meter Management**: Track different types of utility meters (electric, water, gas, heat)
- **Assignment System**: Assign meters to field agents for reading
- **Reading Collection**: Record and verify meter readings with photo evidence
- **Approval Workflow**: Multi-level approval process for meter readings
- **Region Management**: Organize meters and agents by geographical regions
- **Real-time Tracking**: Monitor agent locations and assignment statuses

## Tech Stack

- **Python** 3.9+
- **FastAPI** - Modern, fast web framework
- **SQLAlchemy** - ORM for database interactions
- **PostgreSQL** - Primary database
- **PostGIS** - Geospatial extensions for PostgreSQL
- **Redis** - Caching and rate limiting
- **JWT** - Authentication
- **Alembic** - Database migrations

## Database Schema

### Users
- **id**: UUID (Primary Key)
- **email**: String (Unique, Indexed)
- **password_hash**: String
- **name**: String
- **role**: Enum (admin, manager, agent)
- **status**: Enum (active, inactive, suspended)
- **phone**: String
- **department**: String
- **region**: String
- **permissions**: JSON
- **created_at**: DateTime
- **updated_at**: DateTime
- **last_login**: DateTime

### Agents
- **id**: UUID (Primary Key)
- **user_id**: UUID (Foreign Key to users)
- **location_id**: String
- **current_load**: Integer
- **max_load**: Integer
- **status**: Enum (available, busy, offline, on_break)
- **location**: Geography(Point, 4326)
- **avatar_url**: String
- **created_at**: DateTime
- **updated_at**: DateTime

### Meters
- **id**: UUID (Primary Key)
- **serial_number**: String (Unique, Indexed)
- **address**: Text
- **location_id**: String
- **meter_type**: Enum (electric, water, gas, heat)
- **priority**: Enum (low, medium, high, critical)
- **status**: Enum (active, inactive, maintenance, out_of_service)
- **last_reading**: String
- **estimated_time**: Integer (minutes)
- **coordinates**: Geography(Point, 4326)
- **owner**: String
- **meter_metadata**: JSON
- **created_at**: DateTime
- **updated_at**: DateTime

### MeterReadings
- **id**: UUID (Primary Key)
- **meter_id**: UUID (Foreign Key to meters)
- **agent_id**: UUID (Foreign Key to agents)
- **reading_value**: Float
- **photo_url**: String
- **notes**: Text
- **location**: Geography(Point, 4326)
- **verified**: Boolean
- **reading_timestamp**: DateTime
- **created_at**: DateTime

### MeterAssignments
- **id**: UUID (Primary Key)
- **meter_id**: UUID (Foreign Key to meters)
- **agent_id**: UUID (Foreign Key to agents)
- **status**: Enum (pending, in_progress, completed, cancelled, overdue)
- **estimated_time**: Integer (minutes)
- **assigned_at**: DateTime
- **completed_at**: DateTime
- **completion_notes**: Text

### MeterApprovalRequests
- **id**: UUID (Primary Key)
- **meter_id**: UUID (Foreign Key to meters)
- **agent_id**: UUID (Foreign Key to agents)
- **reviewer_id**: UUID (Foreign Key to users, nullable)
- **meter_data**: JSON
- **status**: Enum (pending, approved, rejected, under_review)
- **submission_notes**: Text
- **review_notes**: Text
- **submitted_at**: DateTime
- **reviewed_at**: DateTime

### Regions
- **id**: UUID (Primary Key)
- **name**: String (Unique, Indexed)
- **description**: Text
- **coordinates**: Geography(Point, 4326)
- **radius**: Float (meters)
- **agent_count**: Integer
- **meter_count**: Integer
- **status**: Enum (active, inactive, maintenance)
- **created_at**: DateTime
- **updated_at**: DateTime

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/utility_meter

# Redis
REDIS_URL=redis://localhost:6379

# JWT
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# File Upload
UPLOAD_DIR=uploads
MAX_FILE_SIZE=10485760  # 10MB in bytes

# CORS (comma-separated if multiple)
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/utility-meter-backend.git
   cd utility-meter-backend
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up the database:
   - Make sure PostgreSQL with PostGIS extension is installed
   - Create a new database for the application
   - Update the `DATABASE_URL` in `.env` with your database credentials

5. Run database migrations:
   ```bash
   alembic upgrade head
   ```

6. Start the development server:
   ```bash
   uvicorn app.main:app --reload
   ```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, you can access:

- **Interactive API docs**: `http://localhost:8000/docs`
- **Alternative API docs**: `http://localhost:8000/redoc`

## Testing

To run tests:

```bash
pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
