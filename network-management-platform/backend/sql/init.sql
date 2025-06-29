-- TimescaleDB initialization
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- UUID extension for generating UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Network-related extensions
CREATE EXTENSION IF NOT EXISTS cidr CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_trgm CASCADE;

-- Create enum types
CREATE TYPE device_status AS ENUM ('online', 'offline', 'warning', 'error', 'unknown');
CREATE TYPE backup_status AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');
CREATE TYPE deployment_status AS ENUM ('pending', 'provisioning', 'installing', 'configuring', 'completed', 'failed');
CREATE TYPE os_type AS ENUM ('ubuntu', 'debian', 'centos', 'rhel', 'windows', 'custom');

-- Grant permissions (will be created when tables are created)
-- This is just a placeholder for future permission grants