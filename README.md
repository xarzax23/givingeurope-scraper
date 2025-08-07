# Giving Europe Scraper

This script scrapes product data from Giving Europe and uploads it to a Supabase database.

## Setup

1.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

2.  **Set up your environment variables:**

    Create a `.env` file in the root of the project and add your Supabase credentials:

    ```
    SUPABASE_URL=your_supabase_url
    SUPABASE_KEY=your_supabase_anon_key
    DB_USER=your_db_user
    DB_PASSWORD=your_db_password
    DB_HOST=your_db_host
    DB_PORT=your_db_port
    DB_NAME=your_db_name
    ```

3.  **The script will automatically create the `products` table if it doesn't exist.**

## Usage

To run the scraper, execute the following command:

```bash
python run_scraper.py
```