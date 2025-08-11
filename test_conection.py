import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# Get the connection string
db_url = os.environ.get("DATABASE_URL")

if not db_url:
    print("❌ ERROR: DATABASE_URL not found in your .env file.", file=sys.stderr)
    sys.exit(1)

print("Attempting to connect to the database...")

try:
    # Try to establish a connection
    conn = psycopg2.connect(db_url)
    print("✅ Success! Connection to the database was successful.")
    # Close the connection
    conn.close()
except psycopg2.Error as e:
    print("❌ Failed to connect to the database.", file=sys.stderr)
    print(f"Error details: {e}", file=sys.stderr)
    sys.exit(1)