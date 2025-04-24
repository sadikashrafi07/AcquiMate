# migration.py - Add this file to your project root
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def run_migration():
    # Connect to database
    DATABASE_URL = os.getenv("DATABASE_URL")
    engine = create_engine(DATABASE_URL)
    
    # Connect and create a transaction
    with engine.connect() as connection:
        with connection.begin():
            # Check if first_name column exists
            result = connection.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'first_name'"
            ))
            first_name_exists = result.scalar() > 0
            
            # Check if last_name column exists
            result = connection.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'last_name'"
            ))
            last_name_exists = result.scalar() > 0
            
            # Check if profile_image column exists
            result = connection.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'profile_image'"
            ))
            profile_image_exists = result.scalar() > 0
            
            # Add first_name column if it doesn't exist
            if not first_name_exists:
                connection.execute(text(
                    "ALTER TABLE users ADD COLUMN first_name VARCHAR(255) NULL"
                ))
                print("Added first_name column")
                
            # Add last_name column if it doesn't exist
            if not last_name_exists:
                connection.execute(text(
                    "ALTER TABLE users ADD COLUMN last_name VARCHAR(255) NULL"
                ))
                print("Added last_name column")
                
            # Add profile_image column if it doesn't exist
            if not profile_image_exists:
                connection.execute(text(
                    "ALTER TABLE users ADD COLUMN profile_image VARCHAR(255) NULL"
                ))
                print("Added profile_image column")
    
    print("Migration completed successfully!")

if __name__ == "__main__":
    run_migration()