# Vehicle Parking App (Modern Application Development I)

## Overview

A multi-user vehicle parking management system built with Flask, Jinja2, Bootstrap, and SQLite. Supports admin and user roles, parking lot/spot management, and reservation history.

## Features

- Admin and user login
- Admin can manage parking lots, view users, flag/unflag users, and view all reservations
- Users can register, book/release parking spots, and view their history
- Responsive UI with Bootstrap
- Database is created programmatically (no manual DB creation)

## Setup Instructions

1. **Clone or extract the project**
2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
3. **Run the app:**
   ```powershell
   python app.py
   ```
4. **Access the app:**
   Open your browser and go to [http://localhost:5173](http://localhost:5173)

## Notes

- The database (`app.db`) is created automatically in the `instance/` folder on first run.
- All core flows (register, login, book, release, view history, admin CRUD) are demoable locally.
