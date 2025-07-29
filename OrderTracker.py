import tkinter as tk
from tkinter import messagebox, filedialog
import requests
from bs4 import BeautifulSoup
import json
import os
import csv

SETTINGS_FILE = "settings.json"

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

        self.save_btn = tk.Button(self.frame, text="Save Credentials", command=self.save_creds)
        self.save_btn.grid(row=2, column=0, columnspan=2, pady=4)

        self.test_btn = tk.Button(self.frame, text="Test Login", command=self.test_login)
        self.test_btn.grid(row=3, column=0, columnspan=2, pady=4)

        tk.Label(self.frame, text="Order Number:").grid(row=4, column=0, sticky="e")
        self.order_entry = tk.Entry(self.frame)
        self.order_entry.grid(row=4, column=1)

        self.scrape_btn = tk.Button(self.frame, text="Scrape & Export Order", command=self.scrape_and_export)
        self.scrape_btn.grid(row=5, column=0, columnspan=2, pady=8)

    def save_creds(self):
        self.settings["username"] = self.username.get()
        self.settings["password"] = self.password.get()
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
        login_url = "https://www.ybsnow.com/login.html"  # update as needed
        data = {
            "username": self.settings.get("username"),
            "password": self.settings.get("password")
        }
        response = session.post(login_url, data=data)
        # Test success logic: update for your site's actual response!
        return "Logout" in response.text or response.url.endswith("/manage.html")

    def scrape_and_export(self):
        order_num = self.order_entry.get().strip()
        if not order_num:
            messagebox.showerror("Missing", "Please enter an order number.")
            return
        
        session = requests.Session()
        if not self.do_login(session):
            messagebox.showerror("Error", "Login failed! Please check credentials.")
            return

        url = "https://www.ybsnow.com/manage.html"
        resp = session.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Scrape table data: You must adjust this for your actual HTML table!
        orders = []
        for row in soup.find_all("tr"):
            cols = [col.text.strip() for col in row.find_all("td")]
            if order_num in "".join(cols):
                orders.append(cols)
        
        if not orders:
            messagebox.showinfo("Not Found", f"Order {order_num} not found.")
            return

        # Save to CSV
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV Files", "*.csv")]
        )
        if file_path:
            with open(file_path, "w", newline='') as csvfile:
                writer = csv.writer(csvfile)
                for row in orders:
                    writer.writerow(row)
            messagebox.showinfo("Done", f"Exported {len(orders)} rows.")

if __name__ == "__main__":
    root = tk.Tk()
    app = YBSScraperApp(root)
    root.mainloop()
