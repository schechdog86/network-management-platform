"""Add snapd management support to devices

Revision ID: add_snapd_support
Revises: 
Create Date: 2024-12-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_snapd_support'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add snapd management columns to devices table
    op.add_column('devices', sa.Column('snapd_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('devices', sa.Column('snapd_endpoint', sa.String(length=255), nullable=True))
    op.add_column('devices', sa.Column('snap_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Create indexes for snapd fields
    op.create_index('idx_devices_snapd_enabled', 'devices', ['snapd_enabled'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('idx_devices_snapd_enabled', table_name='devices')
    
    # Remove snapd management columns
    op.drop_column('devices', 'snap_config')
    op.drop_column('devices', 'snapd_endpoint')
    op.drop_column('devices', 'snapd_enabled')