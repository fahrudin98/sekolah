"""add school activation columns with helper

Revision ID: 00ac0cee1b8e
Revises: ecc2815db3da
Create Date: 2025-05-08 07:27:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '00ac0cee1b8e'
down_revision = 'ecc2815db3da'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Tambah kolom baru ke tabel sekolah
    op.add_column('sekolah', sa.Column('status_aktif', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('sekolah', sa.Column('tanggal_aktivasi', sa.DateTime(), nullable=True))
    op.add_column('sekolah', sa.Column('tanggal_kadaluarsa', sa.DateTime(), nullable=True))
    op.add_column('sekolah', sa.Column('last_warning_sent', sa.Date(), nullable=True))

    # 2. Isi data lama dengan nilai default (aktif sampai 2027-01-01)
    op.execute("""
        UPDATE sekolah 
        SET tanggal_aktivasi = '2026-01-01 00:00:00',
            tanggal_kadaluarsa = '2027-01-01 00:00:00'
        WHERE tanggal_aktivasi IS NULL
    """)

    # 3. Hapus server_default setelah update selesai (opsional, biar tidak mengganggu data baru)
    # Tidak perlu alter column lagi untuk menghindari error


def downgrade():
    op.drop_column('sekolah', 'last_warning_sent')
    op.drop_column('sekolah', 'tanggal_kadaluarsa')
    op.drop_column('sekolah', 'tanggal_aktivasi')
    op.drop_column('sekolah', 'status_aktif')