"""Create users table and add user_id to sessions

Revision ID: 001
Revises: None
Create Date: 2026-02-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('auth_provider', sa.String(20), server_default='local'),
        sa.Column('google_id', sa.String(255), unique=True, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Add user_id FK to sessions (nullable for existing sessions)
    op.add_column('sessions', sa.Column('user_id', sa.String(), nullable=True))
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    op.create_foreign_key('fk_sessions_user_id', 'sessions', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_sessions_user_id', 'sessions', type_='foreignkey')
    op.drop_index('ix_sessions_user_id', table_name='sessions')
    op.drop_column('sessions', 'user_id')
    op.drop_table('users')
