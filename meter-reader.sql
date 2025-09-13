-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- Drop tables in reverse order of dependency
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS meter_approval_requests CASCADE;
DROP TABLE IF EXISTS meter_readings CASCADE;
DROP TABLE IF EXISTS meter_assignments CASCADE;
DROP TABLE IF EXISTS meters CASCADE;
DROP TABLE IF EXISTS agents CASCADE;
DROP TABLE IF EXISTS regions CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create ENUM types
CREATE TYPE user_role AS ENUM ('admin', 'manager', 'agent');
CREATE TYPE user_status AS ENUM ('active', 'inactive', 'suspended');
CREATE TYPE agent_status AS ENUM ('available', 'busy', 'offline', 'on_break');
CREATE TYPE meter_type AS ENUM ('electric', 'water', 'gas', 'heat');
CREATE TYPE meter_priority AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE meter_status AS ENUM ('active', 'inactive', 'maintenance', 'out_of_service');
CREATE TYPE assignment_status AS ENUM ('pending', 'in_progress', 'completed', 'cancelled', 'overdue');
CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected', 'under_review');
CREATE TYPE region_status AS ENUM ('active', 'inactive', 'maintenance');

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'agent',
    status user_status NOT NULL DEFAULT 'active',
    phone VARCHAR(20),
    department VARCHAR(100),
    region VARCHAR(100),
    permissions JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

-- Regions table
CREATE TABLE regions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    coordinates GEOGRAPHY(POINT, 4326),
    radius FLOAT,
    agent_count INTEGER NOT NULL DEFAULT 0,
    meter_count INTEGER NOT NULL DEFAULT 0,
    status region_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Agents table
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    location_id VARCHAR(100),
    current_load INTEGER NOT NULL DEFAULT 0,
    max_load INTEGER NOT NULL DEFAULT 10,
    status agent_status NOT NULL DEFAULT 'available',
    location GEOGRAPHY(POINT, 4326),
    avatar_url VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Meters table
CREATE TABLE meters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    serial_number VARCHAR(255) UNIQUE NOT NULL,
    address TEXT NOT NULL,
    location_id VARCHAR(100),
    meter_type meter_type NOT NULL,
    priority meter_priority NOT NULL DEFAULT 'medium',
    status meter_status NOT NULL DEFAULT 'active',
    last_reading VARCHAR(100),
    estimated_time INTEGER,
    coordinates GEOGRAPHY(POINT, 4326),
    owner VARCHAR(255),
    meter_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Meter assignments table
CREATE TABLE meter_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meter_id UUID NOT NULL REFERENCES meters(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    status assignment_status NOT NULL DEFAULT 'pending',
    estimated_time INTEGER,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    completion_notes TEXT
);

-- Meter readings table
CREATE TABLE meter_readings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meter_id UUID NOT NULL REFERENCES meters(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    reading_value FLOAT NOT NULL,
    photo_url VARCHAR(500),
    notes TEXT,
    location GEOGRAPHY(POINT, 4326),
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    reading_timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Meter approval requests table
CREATE TABLE meter_approval_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meter_id UUID NOT NULL REFERENCES meters(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL,
    meter_data JSONB NOT NULL,
    status approval_status NOT NULL DEFAULT 'pending',
    submission_notes TEXT,
    review_notes TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ
);

-- Audit log table
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    record_id TEXT NOT NULL,
    old_data JSONB,
    new_data JSONB,
    changed_by TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_agents_user_id ON agents(user_id);
CREATE INDEX idx_meters_serial_number ON meters(serial_number);
CREATE INDEX idx_meter_assignments_meter_id ON meter_assignments(meter_id);
CREATE INDEX idx_meter_assignments_agent_id ON meter_assignments(agent_id);
CREATE INDEX idx_meter_readings_meter_id ON meter_readings(meter_id);
CREATE INDEX idx_meter_readings_agent_id ON meter_readings(agent_id);
CREATE INDEX idx_meter_approval_requests_meter_id ON meter_approval_requests(meter_id);
CREATE INDEX idx_meter_approval_requests_agent_id ON meter_approval_requests(agent_id);
CREATE INDEX idx_audit_log_table_name ON audit_log(table_name);
CREATE INDEX idx_audit_log_record_id ON audit_log(record_id);

-- Function to update updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at
BEFORE UPDATE ON agents
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_meters_updated_at
BEFORE UPDATE ON meters
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_regions_updated_at
BEFORE UPDATE ON regions
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to update meter's last_reading
CREATE OR REPLACE FUNCTION update_meter_last_reading()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE meters
    SET last_reading = NEW.reading_value,
        updated_at = NOW()
    WHERE id = NEW.meter_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_meter_last_reading_trigger
AFTER INSERT ON meter_readings
FOR EACH ROW EXECUTE FUNCTION update_meter_last_reading();

-- Function to update agent's current_load
CREATE OR REPLACE FUNCTION update_agent_load()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.agent_id != NEW.agent_id THEN
        UPDATE agents SET current_load = current_load - 1 WHERE id = OLD.agent_id;
        UPDATE agents SET current_load = current_load + 1 WHERE id = NEW.agent_id;
    ELSIF TG_OP = 'INSERT' THEN
        UPDATE agents SET current_load = current_load + 1 WHERE id = NEW.agent_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE agents SET current_load = current_load - 1 WHERE id = OLD.agent_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_agent_load_trigger
AFTER INSERT OR UPDATE OF agent_id OR DELETE ON meter_assignments
FOR EACH ROW EXECUTE FUNCTION update_agent_load();

-- Function to update assignment status when reading is submitted
CREATE OR REPLACE FUNCTION update_assignment_status()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE meter_assignments
    SET status = 'completed',
        completed_at = NOW(),
        completion_notes = 'Auto-completed after reading submission'
    WHERE meter_id = NEW.meter_id 
    AND agent_id = NEW.agent_id 
    AND status = 'in_progress';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_assignment_status_trigger
AFTER INSERT ON meter_readings
FOR EACH ROW EXECUTE FUNCTION update_assignment_status();

-- Function to log audit trail
CREATE OR REPLACE FUNCTION log_audit_trail()
RETURNS TRIGGER AS $$
DECLARE
    operation TEXT;
    old_data JSONB;
    new_data JSONB;
BEGIN
    IF TG_OP = 'INSERT' THEN
        operation := 'INSERT';
        new_data := to_jsonb(NEW);
        old_data := NULL;
    ELSIF TG_OP = 'UPDATE' THEN
        operation := 'UPDATE';
        new_data := to_jsonb(NEW);
        old_data := to_jsonb(OLD);
    ELSIF TG_OP = 'DELETE' THEN
        operation := 'DELETE';
        new_data := NULL;
        old_data := to_jsonb(OLD);
    END IF;
    
    INSERT INTO audit_log (
        table_name,
        operation,
        record_id,
        old_data,
        new_data,
        changed_by
    ) VALUES (
        TG_TABLE_NAME,
        operation,
        COALESCE(NEW.id::TEXT, OLD.id::TEXT),
        old_data,
        new_data,
        current_user
    );
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create audit triggers for all tables
CREATE TRIGGER users_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION log_audit_trail();

CREATE TRIGGER agents_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON agents
FOR EACH ROW EXECUTE FUNCTION log_audit_trail();

CREATE TRIGGER meters_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON meters
FOR EACH ROW EXECUTE FUNCTION log_audit_trail();

CREATE TRIGGER meter_assignments_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON meter_assignments
FOR EACH ROW EXECUTE FUNCTION log_audit_trail();

CREATE TRIGGER meter_readings_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON meter_readings
FOR EACH ROW EXECUTE FUNCTION log_audit_trail();

CREATE TRIGGER meter_approval_requests_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON meter_approval_requests
FOR EACH ROW EXECUTE FUNCTION log_audit_trail();

CREATE TRIGGER regions_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON regions
FOR EACH ROW EXECUTE FUNCTION log_audit_trail();

-- Create a view for active assignments
CREATE VIEW active_assignments AS
SELECT 
    ma.*,
    m.serial_number,
    m.address,
    u.name AS agent_name,
    u.email AS agent_email
FROM 
    meter_assignments ma
    JOIN meters m ON ma.meter_id = m.id
    JOIN agents a ON ma.agent_id = a.id
    JOIN users u ON a.user_id = u.id
WHERE 
    ma.status IN ('pending', 'in_progress');

-- Create a view for meter reading history
CREATE VIEW meter_reading_history AS
SELECT 
    mr.*,
    m.serial_number,
    m.meter_type,
    u.name AS agent_name,
    u.email AS agent_email
FROM 
    meter_readings mr
    JOIN meters m ON mr.meter_id = m.id
    JOIN agents a ON mr.agent_id = a.id
    JOIN users u ON a.user_id = u.id
ORDER BY 
    mr.reading_timestamp DESC;

-- Create a function to get meters that need reading
CREATE OR REPLACE FUNCTION get_meters_needing_reading(days_threshold INTEGER DEFAULT 30)
RETURNS TABLE (
    meter_id UUID,
    serial_number VARCHAR(255),
    address TEXT,
    meter_type meter_type,
    days_since_last_reading NUMERIC,
    priority meter_priority
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id AS meter_id,
        m.serial_number,
        m.address,
        m.meter_type,
        EXTRACT(DAY FROM (NOW() - COALESCE((
            SELECT MAX(reading_timestamp) 
            FROM meter_readings 
            WHERE meter_id = m.id
        ), m.created_at))) AS days_since_last_reading,
        m.priority
    FROM 
        meters m
    WHERE 
        m.status = 'active'::meter_status
        AND (
            NOT EXISTS (
                SELECT 1 
                FROM meter_readings 
                WHERE meter_id = m.id
            )
            OR EXISTS (
                SELECT 1 
                FROM meter_readings 
                WHERE meter_id = m.id
                GROUP BY meter_id
                HAVING MAX(reading_timestamp) < NOW() - (days_threshold * INTERVAL '1 day')
            )
        )
    ORDER BY 
        m.priority DESC,
        days_since_last_reading DESC;
END;
$$ LANGUAGE plpgsql;
