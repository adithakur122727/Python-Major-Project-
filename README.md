# GymDesk — Gym Essentials E-commerce Project (Python + Flask + SQLite)

A complete 3-role e-commerce web app for a **gym essentials store** — Supplements, Bags, Shakers & Vests. Roles: **Customer**, **Seller**, **Admin**.

## Features
- Pre-loaded with **40 gym products** (10 each: Supplements, Bags, Shakers, Vests)
- Customer: browse products, search, filter by category, cart, Cash on Delivery checkout, order tracking
- Seller: register, add/edit/delete own products (image upload or URL), products go to "Pending" until admin approves, view & update order status for their items
- Admin: approve/reject pending products, view all products & stats
- Order status flow updates live: Seller changes status → customer sees it immediately on "My Orders"
- Payment: Cash on Delivery (COD) only — no online payment gateway
- Dark, energetic gym-themed UI (Bootstrap 5 + custom theme) with hover animations, glow effects, and gym photography

---

## 1. Requirements
- Python 3.9+ installed on your computer
- pip (comes with Python)

Check with:
```bash
python --version
pip --version
```

## 2. Setup Steps

**Step 1 — Extract the zip** to any folder, e.g. `Desktop/shopdesk`

**Step 2 — Open terminal / command prompt** inside that folder:
```bash
cd shopdesk
```

**Step 3 — Create a virtual environment (recommended)**
```bash
python -m venv venv
```
Activate it:
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

**Step 4 — Install dependencies**
```bash
pip install -r requirements.txt
```

**Step 5 — Run the app**
```bash
python app.py
```

You'll see:
```
Running on http://127.0.0.1:5000
```

**Step 6 — Open in browser**
Go to: `http://127.0.0.1:5000`

That's it! SQLite database (`shop.db`) is created **automatically** the first time you run the app — no manual SQLite setup needed. Flask-SQLAlchemy handles the connection via this line in `app.py`:
```python
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "shop.db")
```

---

## 3. Demo Logins (auto-created on first run)

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Seller | `rahul_seller` | `seller123` |
| Customer | `priya` | `customer123` |

Or just click **Sign Up** and create your own customer/seller account.

---

## 4. How the Approval Flow Works
1. Seller logs in → **My Products** → **Add Product** (fills details, uploads image)
2. Product status = `Pending` (not visible to customers yet)
3. Admin logs in → **Admin Dashboard** → sees pending product → clicks **Approve** or **Reject**
4. Once approved, product appears on the **Home page** for customers
5. Customer adds to cart → Checkout (enters address + phone, COD only) → Order placed
6. Seller logs in → **Orders** tab → sees the order → updates status (Placed → Confirmed → Shipped → Out for Delivery → Delivered)
7. Customer checks **My Orders** anytime → sees the latest status instantly

---

## 5. Resetting the Database
If you want a fresh start, just delete `shop.db` and run `python app.py` again — it will recreate tables and demo accounts.

```bash
rm shop.db      # Mac/Linux
del shop.db     # Windows
python app.py
```

---

## 6. Project Structure
```
shopdesk/
├── app.py                     # Flask app: models, routes, auth, logic
├── requirements.txt
├── shop.db                    # auto-created SQLite database
├── static/
│   ├── css/style.css          # custom modern theme
│   └── uploads/               # seller-uploaded product images
└── templates/                 # all HTML pages (Jinja2)
    ├── base.html
    ├── index.html
    ├── product.html
    ├── cart.html / checkout.html / order_success.html / my_orders.html
    ├── login.html / signup.html
    ├── seller_dashboard.html / seller_product_form.html / seller_orders.html
    ├── admin_dashboard.html / admin_products.html
    └── error.html
```

## 7. Notes / Next Steps (optional improvements you can add later)
- Add product reviews & ratings
- Add order cancellation by customer
- Add email notifications on status change
- Deploy to a real server (Render / Railway / PythonAnywhere) — swap SQLite for PostgreSQL if scaling up
- Change `app.config["SECRET_KEY"]` in `app.py` before any real deployment
