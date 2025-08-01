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

The program will prompt for YBS credentials. Once logged in, it will periodically scrape order data and store updates in a local SQLite database (`orders.db`). Use the "Scrape & Export Order" button to export an order's history as a CSV file. The interface also includes a **View Orders** button which opens a window showing all order numbers stored in the local database. Selecting an order displays its recorded workstation history, and this window now refreshes whenever new data is scraped so you can watch order progress in real time. A status bar at the bottom of the main window indicates when data was last fetched and parsed so you can confirm the application is actively recording information. The program also maintains a `current_orders` table with the latest timestamps for each workstation. Clicking **Show Order Table** opens a table listing every order and whether it is still active. This view updates automatically whenever new data is scraped.
The login screen also includes a **Base URL** field for the YBS site. If left blank, it defaults to `https://www.ybsnow.com`.

When the application launches it also opens a small browser frame attached to
the right of the main interface. This frame displays `manage.html` from the YBS
site using the `tkinterweb` widget so you can monitor the page directly within
the application. The browser is loaded using the application's authenticated
session so it remains logged in. The scraper always pulls data from
`manage.html`, never from the login page.
