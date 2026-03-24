import sys
import os

# Ensure backend directory is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import engine
from models.models import Base

def sync_db():
    print("Syncing DB schema...")
    Base.metadata.create_all(bind=engine)
    print("DB Synced successfully.")

if __name__ == "__main__":
    sync_db()
