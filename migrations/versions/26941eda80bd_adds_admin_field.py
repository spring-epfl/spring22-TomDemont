"""adds admin field

Revision ID: 26941eda80bd
Revises: 8d6394f53dcf
Create Date: 2022-04-22 11:28:22.985506

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '26941eda80bd'
down_revision = '8d6394f53dcf'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('is_admin', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'is_admin')
    # ### end Alembic commands ###