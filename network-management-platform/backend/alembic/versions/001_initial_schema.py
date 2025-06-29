"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('hashed_password', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Create devices table
    op.create_table('devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=True),
        sa.Column('mac_address', sa.String(length=17), nullable=True),
        sa.Column('device_type', sa.String(length=50), nullable=True),
        sa.Column('vendor', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='unknown'),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('snmp_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('snmp_community', sa.String(length=100), nullable=True),
        sa.Column('snmp_version', sa.Integer(), nullable=True),
        sa.Column('snmp_port', sa.Integer(), nullable=True, server_default='161'),
        sa.Column('snmp_timeout', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('ssh_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ssh_port', sa.Integer(), nullable=True, server_default='22'),
        sa.Column('ssh_username', sa.String(length=100), nullable=True),
        sa.Column('ssh_password', sa.String(length=255), nullable=True),
        sa.Column('ssh_key_path', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_devices_ip_address'), 'devices', ['ip_address'], unique=True)
    op.create_index(op.f('ix_devices_mac_address'), 'devices', ['mac_address'], unique=False)
    op.create_index(op.f('ix_devices_status'), 'devices', ['status'], unique=False)

    # Create device_metrics table (TimescaleDB hypertable)
    op.create_table('device_metrics',
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('metric_type', sa.String(length=50), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('timestamp', 'device_id', 'metric_type')
    )
    op.create_index('idx_device_metrics_device_time', 'device_metrics', ['device_id', 'timestamp'])

    # Create network_scans table
    op.create_table('network_scans',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('subnets', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('scan_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('discovered_devices', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_network_scans_status'), 'network_scans', ['status'])

    # Create ssh_sessions table
    op.create_table('ssh_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('connected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ssh_sessions_session_id'), 'ssh_sessions', ['session_id'], unique=True)

    # Create system_logs table (TimescaleDB hypertable)
    op.create_table('system_logs',
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('level', sa.String(length=10), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('timestamp', 'source')
    )
    op.create_index('idx_system_logs_level', 'system_logs', ['level'])
    op.create_index('idx_system_logs_user', 'system_logs', ['user_id'])

    # Create network_events table (TimescaleDB hypertable)
    op.create_table('network_events',
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('timestamp', 'event_type')
    )
    op.create_index('idx_network_events_device', 'network_events', ['device_id'])
    op.create_index('idx_network_events_severity', 'network_events', ['severity'])

    # Create backup_jobs table
    op.create_table('backup_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('backup_type', sa.String(length=20), nullable=False),
        sa.Column('source_path', sa.String(length=500), nullable=False),
        sa.Column('destination_path', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backup_jobs_status'), 'backup_jobs', ['status'])
    op.create_index(op.f('ix_backup_jobs_device_id'), 'backup_jobs', ['device_id'])

    # Create backup_events table (TimescaleDB hypertable)
    op.create_table('backup_events',
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['backup_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('timestamp', 'job_id', 'event_type')
    )

    # Create pxe_deployments table
    op.create_table('pxe_deployments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('target_mac', sa.String(length=17), nullable=False),
        sa.Column('target_ip', sa.String(length=45), nullable=True),
        sa.Column('os_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pxe_deployments_target_mac'), 'pxe_deployments', ['target_mac'])
    op.create_index(op.f('ix_pxe_deployments_status'), 'pxe_deployments', ['status'])

    # Create dhcp_reservations table
    op.create_table('dhcp_reservations',
        sa.Column('mac_address', sa.String(length=17), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('mac_address')
    )
    op.create_index(op.f('ix_dhcp_reservations_ip_address'), 'dhcp_reservations', ['ip_address'], unique=True)

    # Create dhcp_leases table
    op.create_table('dhcp_leases',
        sa.Column('mac_address', sa.String(length=17), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=True),
        sa.Column('lease_time', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('state', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('mac_address', 'ip_address')
    )
    op.create_index(op.f('ix_dhcp_leases_state'), 'dhcp_leases', ['state'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('dhcp_leases')
    op.drop_table('dhcp_reservations')
    op.drop_table('pxe_deployments')
    op.drop_table('backup_events')
    op.drop_table('backup_jobs')
    op.drop_table('network_events')
    op.drop_table('system_logs')
    op.drop_table('ssh_sessions')
    op.drop_table('network_scans')
    op.drop_table('device_metrics')
    op.drop_table('devices')
    op.drop_table('users')