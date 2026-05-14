"""add_master_tahun_ajaran

Revision ID: a6c0fe2bec7a
Revises: ecc2815db3da
Create Date: 2026-05-10 22:55:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'a6c0fe2bec7a'
down_revision = 'ecc2815db3da'
branch_labels = None
depends_on = None


def upgrade():
    # Buat tabel master_tahun_ajaran
    op.create_table('master_tahun_ajaran',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tahun_ajaran', sa.String(length=20), nullable=False),
        sa.Column('semester', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_global_active', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tahun_ajaran', 'semester', name='uq_master_tahun_semester')
    )
    
    # Tambah kolom master_ta_id ke tahun_ajaran
    with op.batch_alter_table('tahun_ajaran', schema=None) as batch_op:
        batch_op.add_column(sa.Column('master_ta_id', sa.Integer(), nullable=True))
        batch_op.alter_column('tahun_ajaran',
               existing_type=mysql.VARCHAR(length=20),
               nullable=True)
        batch_op.alter_column('semester',
               existing_type=mysql.VARCHAR(length=20),
               nullable=True)
        batch_op.create_foreign_key('fk_tahun_ajaran_master', 'master_tahun_ajaran', ['master_ta_id'], ['id'])
    
    # Migrasi data existing
    op.execute("""
        INSERT INTO master_tahun_ajaran (tahun_ajaran, semester, is_active, created_at)
        SELECT DISTINCT tahun_ajaran, semester, 1, NOW()
        FROM tahun_ajaran
        WHERE tahun_ajaran IS NOT NULL AND semester IS NOT NULL
    """)
    
    op.execute("""
        UPDATE tahun_ajaran ta
        SET ta.master_ta_id = (
            SELECT mta.id 
            FROM master_tahun_ajaran mta 
            WHERE mta.tahun_ajaran = ta.tahun_ajaran 
              AND mta.semester = ta.semester
            LIMIT 1
        )
        WHERE ta.tahun_ajaran IS NOT NULL 
          AND ta.semester IS NOT NULL
    """)


def downgrade():
    with op.batch_alter_table('tahun_ajaran', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tahun_ajaran_master', type_='foreignkey')
        batch_op.alter_column('semester',
               existing_type=mysql.VARCHAR(length=20),
               nullable=False)
        batch_op.alter_column('tahun_ajaran',
               existing_type=mysql.VARCHAR(length=20),
               nullable=False)
        batch_op.drop_column('master_ta_id')
    
    op.drop_table('master_tahun_ajaran')