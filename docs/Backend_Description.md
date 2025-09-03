# Utility Meter Reading Management System — Backend Description

## Overview
FastAPI backend providing authentication, RBAC, agent/meter management, assignments, readings, approvals, regions, files, and reporting. Async stack with PostgreSQL + PostGIS and SQLAlchemy 2.0.

## Architecture
- FastAPI app (`app/main.py`) with versioned routers under `app/api/v1`
- PostgreSQL 15 + PostGIS for geospatial data
- SQLAlchemy 2.0 (async) + GeoAlchemy2
- JWT auth (access/refresh); bcrypt password hashing
- Redis for caching / pub-sub
- File storage Cloudinary on local filesystem (configurable)
- Docker/Docker Compose for local dev

## Configuration
- `app/config.py` uses environment variables for DB, Redis, JWT, CORS, uploads, pagination.
- Default upload dir: `uploads/`.
## Security
- JWT Access (15m) and Refresh (7d). HS256.
- Roles: admin, manager, agent.
- Dependencies: `get_current_user`, `require_manager_or_admin`, `require_admin`, `get_current_agent` for RBAC.
- Passwords hashed via `passlib[bcrypt]`.

## Data Model (Key Entities)
- `User`: id, email, password_hash, name, role, status, phone, department, region, permissions, timestamps.
- `Agent`: id, user_id, location(POINT), current_load, max_load, status, avatar_url, timestamps.
- `Meter`: id, serial_number, address, coordinates(POINT), meter_type, priority, status, last_reading, estimated_time, owner, metadata, timestamps.
- `MeterReading`: id, meter_id, agent_id, reading_value, photo_url, notes, location(POINT), verified, reading_timestamp, timestamps.
- `MeterAssignment`: id, meter_id, agent_id, status, estimated_time, assigned_at, completed_at, completion_notes.
- `MeterApprovalRequest`: id, meter_id, agent_id, reviewer_id, meter_data(JSON), submission_notes, review_notes, status, submitted_at, reviewed_at.
- `Region`: id, name, description, coordinates(POINT), radius, agent_count, meter_count, status, timestamps.
- `AuditLog`: user_id, entity_type, entity_id, action, old_data, new_data, ip, ua, created_at.

## Conventions
- Base URL: `{{baseUrl}}` (e.g., http://localhost:8000)
- API prefix: `/api/v1`
- Auth: `Authorization: Bearer {{accessToken}}`
- Pagination: `page` (default 1), `limit` (default 20, max 100)
- Responses wrapped as `{ success, data, message }`; errors `{ success:false, error, details }`.

## Endpoints

### Auth (`/api/v1/auth`)
- POST `/login`: Body `{ email, password }` → `{access_token, refresh_token, token_type}`
- POST `/refresh`: Body `{ refresh_token }` → new access token
- POST `/logout`: invalidate (client-side token discard)
- GET `/me`: current user profile

### Users (`/api/v1/users`)
- GET `/`: List users; filters: `search`, `role`, `status`, pagination
- GET `/{user_id}`: User by id
- PUT `/{user_id}`: Update user (manager/admin)
- DELETE `/{user_id}`: Soft delete (admin)
- POST `/{user_id}/change-password`: Self or admin; Body `{ current_password?, new_password }`

### Agents (`/api/v1/agents`)
- GET `/`: List agents; filters: `status`, `location_id`, pagination
- POST `/`: Create (manager/admin)
- GET `/{agent_id}`: Details
- PUT `/{agent_id}`: Update
- GET `/{agent_id}/stats`: Performance stats
- GET `/available`: Available agents for assignment
- PUT `/me/location`: Agent updates own GPS `{ latitude, longitude }`
- PUT `/me/status`: Agent updates status

### Meters (`/api/v1/meters`)
- GET `/`: List meters; filters: `status`, `meter_type`, `priority`, `location_id`, `assigned`, `search`
- POST `/`: Create (manager/admin)
- GET `/{meter_id}`: Details
- PUT `/{meter_id}`: Update
- DELETE `/{meter_id}`: Delete if no active assignments
- GET `/nearby`: Query by `lat`, `lng`, `radius`, `limit`
- GET `/unassigned`: Active meters without pending/in_progress assignments

### Readings (`/api/v1/readings`)
- GET `/`: List; filters: `meter_id`, `agent_id`, `verified`, pagination
- POST `/`: Agent submits reading `{ meter_id, reading_value, notes?, photo_url?, location?, reading_timestamp }`
- GET `/{reading_id}`: Details
- PUT `/{reading_id}`: Update (manager/admin)
- GET `/meter/{meter_id}`: History for a meter
- POST `/{reading_id}/verify`: Verify (manager/admin)

### Assignments (`/api/v1/assignments`)
- GET `/`: List; filters: `status`, `agent_id`, `meter_id`, pagination
- POST `/`: Create assignment `{ meter_id, agent_id, estimated_time? }`
- POST `/bulk`: Bulk assign `{ meter_ids:[], agent_id?, estimated_time? }`
- PUT `/{assignment_id}`: Update; auto sets completion timestamps
- GET `/agent/{agent_id}`: Assignments for agent
- PUT `/me/{assignment_id}/status`: Agent updates own assignment status

### Approvals (`/api/v1/approvals`)
- GET `/`: List; filters: `status`, `agent_id`, `meter_id`, pagination
- POST `/`: Agent submits approval request `{ meter_id, meter_data, submission_notes? }`
- GET `/{request_id}`: Details
- PUT `/{request_id}/approve`: Approve (manager/admin), `review_notes?`
- PUT `/{request_id}/reject`: Reject (manager/admin), `review_notes`
- GET `/pending`: Pending approvals

### Regions (`/api/v1/regions`)
- GET `/`: List; filter `status`, pagination
- POST `/`: Create `{ name, description?, location?, radius? }`
- GET `/{region_id}`: Details
- PUT `/{region_id}`: Update
- DELETE `/{region_id}`: Delete
- GET `/{region_id}/stats`: Aggregate stats (basic)

### Files (`/api/v1/files`)
- POST `/upload/photo`: Image upload; returns `{ file_url, filename }`
- POST `/upload/document`: Document upload (manager/admin)
- GET `/{filename}`: Serve file
- DELETE `/{filename}`: Delete file (manager/admin)

### Reports (`/api/v1/reports`)
- GET `/dashboard`: High-level counts & rates
- GET `/agent-performance`: Optional `start_date`, `end_date`
- GET `/meter-status`: Status/type and assignment summary
- GET `/readings-summary`: Optional date range, verified rate
- POST `/export`: Placeholder export `{ report_type, format }`

## Authentication Usage
1) Login to get tokens.
2) Set `Authorization: Bearer {{accessToken}}`.
3) Refresh when access token expires using refresh token.

## Geospatial Notes
- Coordinates stored as PostGIS POINT in SRID 4326.
- Nearby queries via `ST_DWithin`.
- API accepts `{ latitude, longitude }` for locations.

## Error Handling
- 400 invalid input or state; 401 invalid/missing token; 403 insufficient role; 404 not found.

- Swagger UI at `{{baseUrl}}/docs`
- Health at `{{baseUrl}}/health`


