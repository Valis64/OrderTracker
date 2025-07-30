import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext, ttk
import requests
import threading
from bs4 import BeautifulSoup
import json
import os
import csv
import sqlite3
from datetime import datetime
import logging

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
        # allow using the connection from the background update thread
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
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
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS current_orders (
                order_num TEXT PRIMARY KEY,
                indigo TEXT,
                laminate TEXT,
                die_cutting_abg TEXT,
                machine_glue TEXT,
                shipping TEXT,
                last_seen TEXT,
                active INTEGER DEFAULT 1
            )
            """
        )
        self.conn.commit()

        self.session = requests.Session()
        self.create_gui()

        # Load current orders immediately if credentials are available.
        if self.settings.get("username") and self.settings.get("password"):
            try:
                self.update_once()
            except Exception as e:
                logging.exception("Initial load failed: %s", e)
    
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

        self.view_btn = tk.Button(self.frame, text="View Orders", command=self.show_orders_window)
        self.view_btn.grid(row=7, column=0, columnspan=2, pady=4)

        self.fetch_btn = tk.Button(self.frame, text="Fetch Orders Now", command=self.manual_fetch)
        self.fetch_btn.grid(row=8, column=0, columnspan=2, pady=4)

        self.table_btn = tk.Button(self.frame, text="Show Order Table", command=self.show_current_orders)
        self.table_btn.grid(row=9, column=0, columnspan=2, pady=4)

        # last record display
        self.last_frame = tk.Frame(self.root)
        self.last_frame.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(self.last_frame, text="Order #:").grid(row=0, column=0, sticky="e")
        self.last_order_entry = tk.Entry(self.last_frame, state="readonly", width=15)
        self.last_order_entry.grid(row=0, column=1, padx=(0, 10))
        tk.Label(self.last_frame, text="Workstation:").grid(row=0, column=2, sticky="e")
        self.last_ws_entry = tk.Entry(self.last_frame, state="readonly", width=20)
        self.last_ws_entry.grid(row=0, column=3, padx=(0, 10))
        tk.Label(self.last_frame, text="Timestamp:").grid(row=0, column=4, sticky="e")
        self.last_ts_entry = tk.Entry(self.last_frame, state="readonly", width=25)
        self.last_ts_entry.grid(row=0, column=5)

        # log of latest events
        self.log_text = scrolledtext.ScrolledText(self.root, height=10)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

        # activity log to show program operations
        self.activity_text = scrolledtext.ScrolledText(self.root, height=5, state="disabled")
        self.activity_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # status indicator
        self.status_var = tk.StringVar(value="Idle")
        self.status_label = tk.Label(self.root, textvariable=self.status_var, anchor="w")
        self.status_label.pack(fill="x", padx=10, pady=(0, 10))

        self.start_update_loop()

    def save_creds(self):
        self.settings["username"] = self.username.get()
        self.settings["password"] = self.password.get()
        self.settings["base_url"] = self.base_url.get()
        save_settings(self.settings)
        messagebox.showinfo("Saved", "Credentials saved.")

    def test_login(self):
        session = requests.Session()
        username = self.username.get()
        password = self.password.get()
        base_url = self.base_url.get()
        if self.do_login(session, username=username, password=password, base_url=base_url):
            messagebox.showinfo("Login Test", "Login successful!")
        else:
            messagebox.showerror("Login Test", "Login failed.")

    def do_login(self, session, username=None, password=None, base_url=None):
        """Login to the YBS website using details from the live login form."""
        if username is None:
            username = self.settings.get("username")
        if password is None:
            password = self.settings.get("password")
        if base_url is None:
            base_url = self.settings.get("base_url", "https://www.ybsnow.com")

        base = base_url.rstrip("/")

        # Retrieve the login page so we can parse the form and any hidden fields
        try:
            login_page = session.get(base, timeout=10)
        except TypeError:
            login_page = session.get(base)
        except requests.exceptions.RequestException as e:
            logging.error("Failed to fetch login page: %s", e)
            return False
        soup = BeautifulSoup(login_page.text, "html.parser")

        # find a form that contains a password input
        form = None
        for f in soup.find_all("form"):
            if f.find("input", {"type": "password"}):
                form = f
                break
        if not form:
            print("Login form not found on page")
            return False

        action = form.get("action", "/login.html")
        login_url = action if action.startswith("http") else requests.compat.urljoin(base, action)

        data = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            if not name:
                continue
            value = inp.get("value", "")
            if "user" in name.lower():
                data[name] = username
            elif "pass" in name.lower():
                data[name] = password
            else:
                data[name] = value

        try:
            response = session.post(login_url, data=data, timeout=10)
        except TypeError:
            response = session.post(login_url, data=data)
        except requests.exceptions.RequestException as e:
            logging.error("Login request failed: %s", e)
            return False
        logged_in = False
        if response.status_code == 200:
            text_lower = response.text.lower()
            # if the login form still exists, assume failure
            soup_after = BeautifulSoup(response.text, "html.parser")
            login_form = None
            for f in soup_after.find_all("form"):
                if f.find("input", {"type": "password"}):
                    login_form = f
                    break
            if login_form is None:
                logged_in = True
            if "logout" in text_lower or "/manage" in response.url:
                logged_in = True
            if not logged_in:
                # request a known protected page to double check
                try:
                    manage = session.get(f"{base}/manage.html", timeout=10)
                except TypeError:
                    manage = session.get(f"{base}/manage.html")
                except requests.exceptions.RequestException as e:
                    logging.error("Failed to verify login: %s", e)
                    return False
                if manage.status_code == 200 and "login" not in manage.url.lower():
                    logged_in = True
        print(
            f"Login POST to {login_url} returned {response.status_code}, logged_in={logged_in}, url={response.url}"
        )
        return logged_in

    def parse_datetime(self, text):
        """Parse timestamps using several known formats.

        Returns a ``datetime`` object or ``None`` if ``text`` does not match any
        supported format. Unknown strings are logged using ``logging.warning``.
        """

        formats = [
            "%m/%d/%y %H:%M",
            "%m/%d/%y %H:%M:%S",
            "%m/%d/%y %I:%M %p",
            "%m/%d/%y %I:%M:%S %p",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %I:%M:%S %p",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        logging.warning("Unrecognized datetime format: %s", text)
        return None

    def update_orders(self, session):
        base = self.settings.get("base_url", "https://www.ybsnow.com").rstrip("/")
        url = f"{base}/manage.html"
        try:
            resp = session.get(url, timeout=10)
        except TypeError:
            resp = session.get(url)
        except requests.exceptions.RequestException as e:
            logging.error("Failed to update orders: %s", e)
            return 0

        soup = BeautifulSoup(resp.text, "html.parser")

        inserted = 0
        cur = self.conn.cursor()
        seen = set()
        now_iso = datetime.now().isoformat(sep=" ")

        for row in soup.find_all("tr"):
            cols = [col.get_text(strip=True) for col in row.find_all("td")]
            if not cols or not cols[0].startswith("YBS"):
                continue
            parts = cols[0].split()
            if len(parts) < 2:
                logging.warning("Unexpected row format: %s", cols[0])
                continue
            order_num = parts[1]
            seen.add(order_num)
            timestamps = cols[-len(WORKSTATIONS) :]

            values = []
            for ws, ts in zip(WORKSTATIONS, timestamps):
                dt = self.parse_datetime(ts)
                iso = dt.isoformat(sep=" ") if dt else None
                values.append(iso)
                if dt:
                    cur.execute(
                        "INSERT OR IGNORE INTO events(order_num, workstation, timestamp) VALUES(?, ?, ?)",
                        (order_num, ws, iso),
                    )
                    if cur.rowcount:
                        inserted += 1

            cur.execute(
                """
                INSERT INTO current_orders(order_num, indigo, laminate, die_cutting_abg, machine_glue, shipping, last_seen, active)
                VALUES(?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(order_num) DO UPDATE SET
                    indigo=excluded.indigo,
                    laminate=excluded.laminate,
                    die_cutting_abg=excluded.die_cutting_abg,
                    machine_glue=excluded.machine_glue,
                    shipping=excluded.shipping,
                    last_seen=excluded.last_seen,
                    active=1
                """,
                (order_num, *values, now_iso),
            )

        # mark orders that disappeared
        existing = [r[0] for r in cur.execute("SELECT order_num FROM current_orders WHERE active=1")]
        for order in set(existing) - seen:
            cur.execute("UPDATE current_orders SET active=0 WHERE order_num=?", (order,))

        self.conn.commit()
        return inserted

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

    def show_orders_window(self):
        """Display a list of order numbers stored in the database."""
        if getattr(self, "orders_window", None) and self.orders_window.winfo_exists():
            self.orders_window.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("Orders")

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        listbox = tk.Listbox(frame, width=20)
        listbox.pack(side="left", fill="y")

        scrollbar = tk.Scrollbar(frame, command=listbox.yview)
        scrollbar.pack(side="left", fill="y")
        listbox.config(yscrollcommand=scrollbar.set)

        details = scrolledtext.ScrolledText(frame, width=50)
        details.pack(side="left", fill="both", expand=True, padx=(10, 0))

        self.orders_window = win
        self.orders_listbox = listbox
        self.orders_details = details

        cur = self.conn.cursor()
        order_nums = [row[0] for row in cur.execute("SELECT DISTINCT order_num FROM events ORDER BY order_num")]
        for num in order_nums:
            listbox.insert(tk.END, num)

        def on_select(event=None):
            sel = listbox.curselection()
            if not sel:
                return
            order = listbox.get(sel[0])
            self.update_order_details(order)

        self.orders_on_select = on_select
        listbox.bind("<<ListboxSelect>>", on_select)

        def on_close():
            self.orders_window = None
            win.destroy()

        tk.Button(win, text="Close", command=on_close).pack(pady=4)

        win.protocol("WM_DELETE_WINDOW", on_close)

    def update_order_details(self, order_num):
        """Populate the details pane for ``order_num``."""
        if not getattr(self, "orders_details", None):
            return
        data = self.get_order_data(order_num)
        self.orders_details.delete("1.0", tk.END)
        for ws, end_time, dur in data:
            dur_str = f"{dur:.2f}" if dur is not None else ""
            self.orders_details.insert(tk.END, f"{ws} - {end_time} - {dur_str}\n")

    def refresh_orders_window(self):
        """Update the order list and details pane if the window is open."""
        if not getattr(self, "orders_window", None):
            return
        if not self.orders_window.winfo_exists():
            self.orders_window = None
            return

        listbox = self.orders_listbox
        cur_selection = listbox.curselection()
        selected = listbox.get(cur_selection[0]) if cur_selection else None

        cur = self.conn.cursor()
        order_nums = [row[0] for row in cur.execute("SELECT DISTINCT order_num FROM events ORDER BY order_num")]

        listbox.delete(0, tk.END)
        for num in order_nums:
            listbox.insert(tk.END, num)

        if selected and selected in order_nums:
            idx = order_nums.index(selected)
            listbox.selection_set(idx)
            listbox.activate(idx)
            self.update_order_details(selected)

    def show_current_orders(self):
        """Display a table of the latest order status."""
        if getattr(self, "order_table_win", None) and self.order_table_win.winfo_exists():
            self.order_table_win.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("Current Orders")

        columns = [
            "order_num",
            "indigo",
            "laminate",
            "die_cutting_abg",
            "machine_glue",
            "shipping",
            "last_seen",
            "active",
        ]
        headings = [
            "Order",
            "Indigo",
            "Laminate",
            "Die Cutting ABG",
            "Machine Glue",
            "Shipping",
            "Last Seen",
            "Active",
        ]

        tree = ttk.Treeview(win, columns=columns, show="headings")
        for col, head in zip(columns, headings):
            tree.heading(col, text=head)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.order_table_win = win
        self.order_tree = tree

        self.populate_current_orders()

        def on_close():
            self.order_table_win = None
            self.order_tree = None
            win.destroy()

        tk.Button(win, text="Close", command=on_close).pack(pady=4)

        win.protocol("WM_DELETE_WINDOW", on_close)

    def populate_current_orders(self):
        if not getattr(self, "order_tree", None):
            return
        tree = self.order_tree
        cur = self.conn.cursor()
        rows = list(
            cur.execute(
                """
                SELECT order_num, indigo, laminate, die_cutting_abg, machine_glue,
                       shipping, last_seen, active
                FROM current_orders ORDER BY order_num
                """
            )
        )
        tree.delete(*tree.get_children())
        for row in rows:
            display = list(row)
            display[-1] = "Yes" if row[-1] else "No"
            tree.insert("", tk.END, values=display)

    def refresh_current_orders(self):
        self.populate_current_orders()

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

    def refresh_last_record(self):
        cur = self.conn.cursor()
        row = cur.execute(
            "SELECT order_num, workstation, timestamp FROM events ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        values = row if row else ("", "", "")
        widgets = [self.last_order_entry, self.last_ws_entry, self.last_ts_entry]
        for widget, value in zip(widgets, values):
            widget.config(state="normal")
            widget.delete(0, tk.END)
            widget.insert(0, value)
            widget.config(state="readonly")

    def log_activity(self, message):
        """Append a timestamped message to the activity log."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.activity_text.config(state="normal")
        self.activity_text.insert(tk.END, f"{ts} - {message}\n")
        self.activity_text.see(tk.END)
        self.activity_text.config(state="disabled")

    def ensure_login(self):
        """Make sure the session is logged in. Return True on success."""
        if not self.do_login(self.session):
            # start a new session and try again
            self.session = requests.Session()
            if not self.do_login(self.session):
                return False
        return True

    def update_once(self, silent=False):
        """Fetch the manage page and update order data."""
        self.status_var.set("Updating...")
        self.log_activity("Fetching orders")
        if self.ensure_login():
            new_events = self.update_orders(self.session)
            # fetch page to keep session current but ignore contents
            base = self.settings.get("base_url", "https://www.ybsnow.com").rstrip("/")
            try:
                self.session.get(f"{base}/manage.html", timeout=10)
            except TypeError:
                self.session.get(f"{base}/manage.html")
            except Exception:
                pass
            self.refresh_log_display()
            self.refresh_last_record()
            self.refresh_orders_window()
            self.refresh_current_orders()
            self.status_var.set(
                f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.log_activity(f"Update complete ({new_events} new events)")
        else:
            if not silent:
                messagebox.showerror("Login Failed", "Could not log in to YBS.")
            else:
                logging.error("Could not log in to YBS.")
            self.status_var.set("Update failed")
            self.log_activity("Login failed")

    def update_loop(self):
        threading.Thread(target=lambda: self.update_once(silent=True), daemon=True).start()
        self.root.after(60000, self.update_loop)

    def start_update_loop(self):
        self.root.after(0, self.update_loop)

    def manual_fetch(self):
        """Handler for the Fetch Orders Now button."""
        self.update_once()

    def scrape_and_export(self):
        order_num = self.order_entry.get().strip()
        if not order_num:
            messagebox.showerror("Missing", "Please enter an order number.")
            return

        if not self.ensure_login():
            messagebox.showerror("Error", "Login failed! Please check credentials.")
            return

        self.update_orders(self.session)

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
