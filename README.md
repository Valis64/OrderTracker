# OrderTracker

A Tkinter-based GUI application for tracking YBS orders. The script logs into the YBS website, scrapes order information, stores it in a SQLite database, and allows exporting order data to CSV. The login routine parses the live login form and checks a protected page to verify successful authentication.

## Requirements

- Python 3
- See `requirements.txt` for Python package dependencies.

## Setup

1. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   python OrderTracker.py
   ```

The program will prompt for YBS credentials. Once logged in, it will periodically scrape order data and store updates in a local SQLite database (`orders.db`). Use the "Scrape & Export Order" button to export an order's history as a CSV file. The interface also includes a **View Orders** button which opens a window showing all order numbers stored in the local database. Selecting an order displays its recorded workstation history. A status bar at the bottom of the main window indicates when data was last fetched and parsed so you can confirm the application is actively recording information.
The login screen also includes a **Base URL** field for the YBS site. If left blank, it defaults to `https://www.ybsnow.com`.
