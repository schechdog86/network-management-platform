-- Network Management Database Schema Initialization

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS devices;
CREATE SCHEMA IF NOT EXISTS metrics;
CREATE SCHEMA IF NOT EXISTS ai;
CREATE SCHEMA IF NOT EXISTS auth;

-- Devices table
CREATE TABLE IF NOT EXISTS devices.devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    ip_address INET NOT NULL,
    mac_address MACADDR,
    device_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'unknown',
    location VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Device metrics table (time-series)
CREATE TABLE IF NOT EXISTS metrics.device_metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id UUID NOT NULL REFERENCES devices.devices(id),
    metric_type VARCHAR(50) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);

-- Convert to hypertable
SELECT create_hypertable('metrics.device_metrics', 'time');

-- Create indexes
CREATE INDEX idx_device_metrics_device_time ON metrics.device_metrics (device_id, time DESC);
CREATE INDEX idx_device_metrics_type ON metrics.device_metrics (metric_type, time DESC);

-- Network metrics table
CREATE TABLE IF NOT EXISTS metrics.network_metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id UUID NOT NULL REFERENCES devices.devices(id),
    interface VARCHAR(50) NOT NULL,
    bytes_sent BIGINT,
    bytes_received BIGINT,
    packets_sent BIGINT,
    packets_received BIGINT,
    errors_in INTEGER DEFAULT 0,
    errors_out INTEGER DEFAULT 0,
    dropped_in INTEGER DEFAULT 0,
    dropped_out INTEGER DEFAULT 0
);

SELECT create_hypertable('metrics.network_metrics', 'time');

-- GPU metrics table
CREATE TABLE IF NOT EXISTS metrics.gpu_metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id UUID NOT NULL REFERENCES devices.devices(id),
    gpu_index INTEGER NOT NULL,
    gpu_name VARCHAR(255),
    temperature REAL,
    gpu_utilization REAL,
    memory_utilization REAL,
    memory_used BIGINT,
    memory_total BIGINT,
    power_draw REAL,
    power_limit REAL
);

SELECT create_hypertable('metrics.gpu_metrics', 'time');

-- AI Jobs table
CREATE TABLE IF NOT EXISTS ai.jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    device_id UUID REFERENCES devices.devices(id),
    model_name VARCHAR(255),
    parameters JSONB DEFAULT '{}',
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

-- AI Job metrics
CREATE TABLE IF NOT EXISTS ai.job_metrics (
    time TIMESTAMPTZ NOT NULL,
    job_id UUID NOT NULL REFERENCES ai.jobs(id),
    metric_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);

SELECT create_hypertable('ai.job_metrics', 'time');

-- Backup records
CREATE TABLE IF NOT EXISTS devices.backups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id UUID NOT NULL REFERENCES devices.devices(id),
    backup_type VARCHAR(50) NOT NULL,
    file_path VARCHAR(500),
    file_size BIGINT,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

-- Users table
CREATE TABLE IF NOT EXISTS auth.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

-- API Keys
CREATE TABLE IF NOT EXISTS auth.api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id),
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    scopes TEXT[] DEFAULT '{}',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used TIMESTAMPTZ
);

-- Audit log
CREATE TABLE IF NOT EXISTS auth.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create continuous aggregates for common queries
CREATE MATERIALIZED VIEW metrics.device_metrics_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS hour,
    device_id,
    metric_type,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value,
    COUNT(*) as sample_count
FROM metrics.device_metrics
GROUP BY hour, device_id, metric_type;

-- Add retention policy (keep raw data for 30 days)
SELECT add_retention_policy('metrics.device_metrics', INTERVAL '30 days');
SELECT add_retention_policy('metrics.network_metrics', INTERVAL '30 days');
SELECT add_retention_policy('metrics.gpu_metrics', INTERVAL '30 days');
SELECT add_retention_policy('ai.job_metrics', INTERVAL '90 days');

-- Create indexes for performance
CREATE INDEX idx_devices_status ON devices.devices(status);
CREATE INDEX idx_devices_type ON devices.devices(device_type);
CREATE INDEX idx_jobs_status ON ai.jobs(status, created_at DESC);
CREATE INDEX idx_audit_log_user ON auth.audit_log(user_id, created_at DESC);

-- Create default admin user (password: admin - CHANGE IN PRODUCTION)
INSERT INTO auth.users (username, email, hashed_password, is_superuser)
VALUES ('admin', 'admin@networkmanager.local', 
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN4LyRo6EkNc7pFl3loiu', true)
ON CONFLICT (username) DO NOTHING;