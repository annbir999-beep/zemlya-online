# Import all models so SQLAlchemy can resolve relationships
from models.lot import Lot  # noqa
from models.user import User, SavedLot, LotView  # noqa
from models.alert import Alert  # noqa
