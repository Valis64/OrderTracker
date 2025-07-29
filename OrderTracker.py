import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
from tkhtmlview import HTMLLabel
import requests
from bs4 import BeautifulSoup
import json
import os
import csv
import sqlite3
from datetime import datetime

SETTINGS_FILE = "settings.json"
DB_FILE = "orders.db"
WORKSTATIONS = [
    "Indigo",
    "Laminate",
    "Die Cutting ABG",
    "Machine Glue",
    "Shipping",
]

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

class YBSScraperApp:
    def __init__(self, root):
        self.root = root
        root.title("YBS Order Scraper")
        self.settings = load_settings()

        # database setup
        self.conn = sqlite3.connect(DB_FILE)
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                order_num TEXT,
                workstation TEXT,
                timestamp TEXT,
                UNIQUE(order_num, workstation, timestamp)
            )
            """
        )
        self.conn.commit()

        self.create_gui()
    
    def create_gui(self):
        self.frame = tk.Frame(self.root)
        self.frame.pack(padx=10, pady=10)

        tk.Label(self.frame, text="YBS Username:").grid(row=0, column=0, sticky="e")
        self.username = tk.Entry(self.frame)
        self.username.grid(row=0, column=1)
        self.username.insert(0, self.settings.get("username", ""))

        tk.Label(self.frame, text="YBS Password:").grid(row=1, column=0, sticky="e")
        self.password = tk.Entry(self.frame, show="*")
        self.password.grid(row=1, column=1)
        self.password.insert(0, self.settings.get("password", ""))

        tk.Label(self.frame, text="Base URL:").grid(row=2, column=0, sticky="e")
        self.base_url = tk.Entry(self.frame)
        self.base_url.grid(row=2, column=1)
        self.base_url.insert(0, self.settings.get("base_url", "https://www.ybsnow.com"))

        self.save_btn = tk.Button(self.frame, text="Save Credentials", command=self.save_creds)
        self.save_btn.grid(row=3, column=0, columnspan=2, pady=4)
        self.test_btn = tk.Button(self.frame, text="Test Login", command=self.test_login)
        self.test_btn.grid(row=4, column=0, columnspan=2, pady=4)
        tk.Label(self.frame, text="Order Number:").grid(row=5, column=0, sticky="e")
        self.order_entry = tk.Entry(self.frame)
        self.order_entry.grid(row=5, column=1)
        self.scrape_btn = tk.Button(self.frame, text="Scrape & Export Order", command=self.scrape_and_export)
        self.scrape_btn.grid(row=6, column=0, columnspan=2, pady=8)

        # HTML preview
        self.web = HTMLLabel(self.root, html="")
        self.web.pack(fill="both", expand=True, padx=10, pady=10)

        # log of latest events
        self.log_text = scrolledtext.ScrolledText(self.root, height=10)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

        self.start_update_loop()

    def save_creds(self):
        self.settings["username"] = self.username.get()
        self.settings["password"] = self.password.get()
        self.settings["base_url"] = self.base_url.get()
        save_settings(self.settings)
        messagebox.showinfo("Saved", "Credentials saved.")

    def test_login(self):
        session = requests.Session()
        if self.do_login(session):
            messagebox.showinfo("Login Test", "Login successful!")
        else:
            messagebox.showerror("Login Test", "Login failed.")

    def do_login(self, session):
        # Adjust login logic to match the website form fields!
        base = self.settings.get("base_url", "https://www.ybsnow.com").rstrip("/")
        login_url = f"{base}/login.html"
        data = {
            "username": self.settings.get("username"),
            "password": self.settings.get("password")
        }
        response = session.post(login_url, data=data)
        # Test success logic: update for your site's actual response!
        return "Logout" in response.text or response.url.endswith("/manage.html")

    def parse_datetime(self, text):
        try:
            return datetime.strptime(text, "%m/%d/%y %H:%M")
        except Exception:
            return None

    def update_orders(self, session):
        base = self.settings.get("base_url", "https://www.ybsnow.com").rstrip("/")
        url = f"{base}/manage.html"
        resp = session.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        for row in soup.find_all("tr"):
            cols = [col.get_text(strip=True) for col in row.find_all("td")]
            if not cols:
                continue
            if not cols[0].startswith("YBS"):
                continue
            order_num = cols[0].split()[1]
            timestamps = cols[-len(WORKSTATIONS) :]
            for ws, ts in zip(WORKSTATIONS, timestamps):
                dt = self.parse_datetime(ts)
                if not dt:
                    continue
                iso = dt.isoformat(sep=" ")
                cur = self.conn.cursor()
                cur.execute(
                    "INSERT OR IGNORE INTO events(order_num, workstation, timestamp) VALUES(?, ?, ?)",
                    (order_num, ws, iso),
                )
                self.conn.commit()

    def get_order_data(self, order_num):
        cur = self.conn.cursor()
        rows = list(
            cur.execute(
                "SELECT workstation, timestamp FROM events WHERE order_num=? ORDER BY timestamp",
                (order_num,),
            )
        )
        if not rows:
            return []

        parsed = [(ws, datetime.fromisoformat(ts)) for ws, ts in rows]
        results = []
        for i, (ws, dt) in enumerate(parsed):
            dur = None
            if i + 1 < len(parsed):
                dur = (parsed[i + 1][1] - dt).total_seconds() / 3600.0
            results.append((ws, dt.strftime("%m/%d/%y %H:%M"), dur))
        return results

    def refresh_log_display(self):
        cur = self.conn.cursor()
        rows = list(
            cur.execute(
                "SELECT order_num, workstation, timestamp FROM events ORDER BY timestamp DESC LIMIT 10"
            )
        )
        self.log_text.delete("1.0", tk.END)
        for order_num, ws, ts in rows:
            self.log_text.insert(tk.END, f"{order_num} - {ws} - {ts}\n")

    def update_loop(self):
        session = requests.Session()
        if self.do_login(session):
            self.update_orders(session)
            try:
                base = self.settings.get("base_url", "https://www.ybsnow.com").rstrip("/")
                page = session.get(f"{base}/manage.html")
                self.web.set_html(page.text)
            except Exception:
                pass
            self.refresh_log_display()
        self.root.after(60000, self.update_loop)

    def start_update_loop(self):
        self.root.after(0, self.update_loop)

    def scrape_and_export(self):
        order_num = self.order_entry.get().strip()
        if not order_num:
            messagebox.showerror("Missing", "Please enter an order number.")
            return

        session = requests.Session()
        if not self.do_login(session):
            messagebox.showerror("Error", "Login failed! Please check credentials.")
            return

        self.update_orders(session)

        data = self.get_order_data(order_num)
        if not data:
            messagebox.showinfo("Not Found", f"Order {order_num} not found in database.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV Files", "*.csv")]
        )
        if file_path:
            with open(file_path, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Workstation", "Completed", "Time At Station (hours)"])
                for ws, end_time, dur in data:
                    writer.writerow([ws, end_time, f"{dur:.2f}" if dur is not None else ""])
            messagebox.showinfo("Done", f"Exported order {order_num} data.")

if __name__ == "__main__":
    root = tk.Tk()
    app = YBSScraperApp(root)
    root.mainloop()
