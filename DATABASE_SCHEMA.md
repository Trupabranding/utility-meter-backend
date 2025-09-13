# Database Schema Documentation

## Table of Contents
1. [Users](#users)
2. [Agents](#agents)
3. [Meters](#meters)
4. [MeterReadings](#meterreadings)
5. [MeterAssignments](#meterassignments)
6. [MeterApprovalRequests](#meterapprovalrequests)
7. [Regions](#regions)

## Users
Stores user accounts with authentication and authorization details.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | NOT NULL | Primary key |
| email | String(255) | NOT NULL | Unique user email |
| password_hash | String(255) | NOT NULL | Hashed password |
| name | String(255) | NOT NULL | User's full name |
| role | Enum(admin, manager, agent) | NOT NULL | User role |
| status | Enum(active, inactive, suspended) | NOT NULL | Account status |
| phone | String(20) | NULL | Contact number |
| department | String(100) | NULL | User's department |
| region | String(100) | NULL | Geographical region |
| permissions | JSON | NULL | User permissions |
| created_at | DateTime | NOT NULL | Account creation timestamp |
| updated_at | DateTime | NOT NULL | Last update timestamp |
| last_login | DateTime | NULL | Last login timestamp |

**Indexes:**
- Primary Key: `id`
- Unique: `email`

## Agents
Represents field agents who collect meter readings.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | NOT NULL | Primary key |
| user_id | UUID | NOT NULL | Reference to users.id |
| location_id | String(100) | NULL | External location identifier |
| current_load | Integer | NOT NULL | Current number of active assignments |
| max_load | Integer | NOT NULL | Maximum assignments agent can handle |
| status | Enum(available, busy, offline, on_break) | NOT NULL | Agent's availability status |
| location | Geography(Point, 4326) | NULL | Current geographical location |
| avatar_url | String(500) | NULL | URL to agent's profile picture |
| created_at | DateTime | NOT NULL | Record creation timestamp |
| updated_at | DateTime | NOT NULL | Last update timestamp |

**Indexes:**
- Primary Key: `id`
- Foreign Key: `user_id` → `users.id`

## Meters
Stores information about utility meters.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | NOT NULL | Primary key |
| serial_number | String(255) | NOT NULL | Unique meter identifier |
| address | Text | NOT NULL | Physical location address |
| location_id | String(100) | NULL | External location identifier |
| meter_type | Enum(electric, water, gas, heat) | NOT NULL | Type of utility meter |
| priority | Enum(low, medium, high, critical) | NOT NULL | Reading priority |
| status | Enum(active, inactive, maintenance, out_of_service) | NOT NULL | Meter status |
| last_reading | String(100) | NULL | Last recorded reading |
| estimated_time | Integer | NULL | Estimated reading time in minutes |
| coordinates | Geography(Point, 4326) | NULL | Geographical coordinates |
| owner | String(255) | NULL | Meter owner information |
| meter_metadata | JSON | NULL | Additional meter data |
| created_at | DateTime | NOT NULL | Record creation timestamp |
| updated_at | DateTime | NOT NULL | Last update timestamp |

**Indexes:**
- Primary Key: `id`
- Unique: `serial_number`

## MeterReadings
Records of meter readings taken by agents.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | NOT NULL | Primary key |
| meter_id | UUID | NOT NULL | Reference to meters.id |
| agent_id | UUID | NOT NULL | Reference to agents.id |
| reading_value | Float | NOT NULL | The actual meter reading |
| photo_url | String(500) | NULL | URL to reading photo |
| notes | Text | NULL | Additional notes |
| location | Geography(Point, 4326) | NULL | Location where reading was taken |
| verified | Boolean | NOT NULL | Whether reading was verified |
| reading_timestamp | DateTime | NOT NULL | When reading was taken |
| created_at | DateTime | NOT NULL | Record creation timestamp |

**Indexes:**
- Primary Key: `id`
- Foreign Keys:
  - `meter_id` → `meters.id`
  - `agent_id` → `agents.id`

## MeterAssignments
Tracks which meters are assigned to which agents.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | NOT NULL | Primary key |
| meter_id | UUID | NOT NULL | Reference to meters.id |
| agent_id | UUID | NOT NULL | Reference to agents.id |
| status | Enum(pending, in_progress, completed, cancelled, overdue) | NOT NULL | Assignment status |
| estimated_time | Integer | NULL | Estimated completion time in minutes |
| assigned_at | DateTime | NOT NULL | When assignment was created |
| completed_at | DateTime | NULL | When assignment was completed |
| completion_notes | Text | NULL | Notes about completion |

**Indexes:**
- Primary Key: `id`
- Foreign Keys:
  - `meter_id` → `meters.id`
  - `agent_id` → `agents.id`

## MeterApprovalRequests
Tracks approval workflow for meter readings.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | NOT NULL | Primary key |
| meter_id | UUID | NOT NULL | Reference to meters.id |
| agent_id | UUID | NOT NULL | Reference to agents.id |
| reviewer_id | UUID | NULL | Reference to users.id |
| meter_data | JSON | NOT NULL | Snapshot of meter data |
| status | Enum(pending, approved, rejected, under_review) | NOT NULL | Approval status |
| submission_notes | Text | NULL | Notes from submitter |
| review_notes | Text | NULL | Notes from reviewer |
| submitted_at | DateTime | NOT NULL | When request was submitted |
| reviewed_at | DateTime | NULL | When request was reviewed |

**Indexes:**
- Primary Key: `id`
- Foreign Keys:
  - `meter_id` → `meters.id`
  - `agent_id` → `agents.id`
  - `reviewer_id` → `users.id`

## Regions
Defines geographical regions for organizing meters and agents.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | NOT NULL | Primary key |
| name | String(255) | NOT NULL | Region name |
| description | Text | NULL | Region description |
| coordinates | Geography(Point, 4326) | NULL | Center point of region |
| radius | Float | NULL | Region radius in meters |
| agent_count | Integer | NOT NULL | Number of agents in region |
| meter_count | Integer | NOT NULL | Number of meters in region |
| status | Enum(active, inactive, maintenance) | NOT NULL | Region status |
| created_at | DateTime | NOT NULL | Record creation timestamp |
| updated_at | DateTime | NOT NULL | Last update timestamp |

**Indexes:**
- Primary Key: `id`
- Unique: `name`

## Entity Relationship Diagram

```
+-------------+       +-------------+       +-------------+
|    Users    |       |   Agents    |       |   Meters    |
+-------------+       +-------------+       +-------------+
| PK id      |<------| PK id      |       | PK id      |
|   ...      |       | FK user_id |       |   ...      |
+------------+        +------------+        +------------+
     ^                      |                     |
     |                      |                     |
     |               +------+------+              |
     |               |             |              |
     |               v             v              |
     |        +-------------+    +-------------+  |
     |        | Assignments |    |  Readings   |  |
     |        +-------------+    +-------------+  |
     |        | PK id      |    | PK id      |  |
     |        | FK meter_id|    | FK meter_id|  |
     |        | FK agent_id|    | FK agent_id|  |
     |        +------------+    +------------+  |
     |                                           |
     |        +-------------+                    |
     +--------|  Approvals |                    |
              +-------------+                    |
              | PK id      |                    |
              | FK meter_id|                    |
              | FK agent_id|                    |
              | FK reviewer_id (Users)          |
              +------------+                    |
                                              |
                                       +-------------+
                                       |   Regions   |
                                       +-------------+
                                       | PK id      |
                                       |   ...      |
                                       +------------+
```

## Notes

1. **Geospatial Data**: The system uses PostGIS for geospatial capabilities. All location data is stored using SRID 4326 (WGS84).

2. **Soft Deletes**: The schema doesn't implement soft deletes. Consider adding an `is_deleted` flag and `deleted_at` timestamp if needed.

3. **Audit Trail**: Consider adding a dedicated audit log table to track all changes to critical data.

4. **Indexing**: Review and add appropriate indexes based on query patterns in production.

5. **Partitioning**: For high-volume tables (like meter_readings), consider table partitioning by date ranges.
