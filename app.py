import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "shop.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please login to continue."
login_manager.login_message_category = "warning"

ORDER_STATUSES = ["Placed", "Confirmed", "Shipped", "Out for Delivery", "Delivered", "Cancelled"]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")  # customer / seller / admin
    shop_name = db.Column(db.String(120))  # only for sellers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(255), default="")
    category = db.Column(db.String(80), default="General")
    status = db.Column(db.String(20), default="pending")  # pending / approved / rejected
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    seller = db.relationship("User", backref="products")


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    address = db.Column(db.String(300), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    payment_method = db.Column(db.String(20), default="COD")
    total_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("User", backref="orders")
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default="Placed")

    seller = db.relationship("User", foreign_keys=[seller_id])


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Helpers / decorators
# ---------------------------------------------------------------------------
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def get_cart():
    return session.get("cart", {})  # {product_id_str: qty}


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    query = Product.query.filter_by(status="approved")
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    if category:
        query = query.filter_by(category=category)
    products = query.order_by(Product.created_at.desc()).all()
    categories = [c[0] for c in db.session.query(Product.category).filter_by(status="approved").distinct()]
    return render_template("index.html", products=products, q=q, categories=categories, active_category=category)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    if product.status != "approved" and (not current_user.is_authenticated or current_user.id != product.seller_id):
        if not (current_user.is_authenticated and current_user.role == "admin"):
            abort(404)
    return render_template("product.html", product=product)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        role = request.form.get("role", "customer")
        shop_name = request.form.get("shop_name", "").strip()

        if role not in ("customer", "seller"):
            role = "customer"

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already registered.", "danger")
            return redirect(url_for("signup"))

        user = User(username=username, email=email, role=role, shop_name=shop_name or None)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.username}!", "success")
            next_page = request.args.get("next")
            if user.role == "admin":
                return redirect(next_page or url_for("admin_dashboard"))
            elif user.role == "seller":
                return redirect(next_page or url_for("seller_dashboard"))
            return redirect(next_page or url_for("index"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Cart & Checkout (customer)
# ---------------------------------------------------------------------------
@app.route("/cart")
def cart():
    cart_dict = get_cart()
    items = []
    total = 0
    for pid, qty in cart_dict.items():
        product = Product.query.get(int(pid))
        if product:
            subtotal = product.price * qty
            total += subtotal
            items.append({"product": product, "qty": qty, "subtotal": subtotal})
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id):
    product = Product.query.get_or_404(product_id)
    qty = int(request.form.get("quantity", 1))
    cart_dict = get_cart()
    current_qty = cart_dict.get(str(product_id), 0) + qty
    if current_qty > product.stock:
        current_qty = product.stock
    cart_dict[str(product_id)] = max(current_qty, 1)
    save_cart(cart_dict)
    flash(f"{product.name} added to cart.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def cart_update(product_id):
    qty = int(request.form.get("quantity", 1))
    cart_dict = get_cart()
    if qty <= 0:
        cart_dict.pop(str(product_id), None)
    else:
        cart_dict[str(product_id)] = qty
    save_cart(cart_dict)
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:product_id>")
def cart_remove(product_id):
    cart_dict = get_cart()
    cart_dict.pop(str(product_id), None)
    save_cart(cart_dict)
    flash("Item removed from cart.", "info")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    if current_user.role != "customer":
        flash("Only customer accounts can place orders.", "warning")
        return redirect(url_for("index"))

    cart_dict = get_cart()
    if not cart_dict:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("index"))

    items = []
    total = 0
    for pid, qty in cart_dict.items():
        product = Product.query.get(int(pid))
        if product:
            subtotal = product.price * qty
            total += subtotal
            items.append({"product": product, "qty": qty, "subtotal": subtotal})

    if request.method == "POST":
        address = request.form["address"].strip()
        phone = request.form["phone"].strip()

        order = Order(customer_id=current_user.id, address=address, phone=phone,
                       payment_method="COD", total_amount=total)
        db.session.add(order)
        db.session.flush()  # get order.id

        for entry in items:
            product = entry["product"]
            item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                seller_id=product.seller_id,
                product_name=product.name,
                price=product.price,
                quantity=entry["qty"],
                status="Placed",
            )
            product.stock = max(product.stock - entry["qty"], 0)
            db.session.add(item)

        db.session.commit()
        save_cart({})
        return redirect(url_for("order_success", order_id=order.id))

    return render_template("checkout.html", items=items, total=total)


@app.route("/order/success/<int:order_id>")
@login_required
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != current_user.id:
        abort(403)
    return render_template("order_success.html", order=order)


@app.route("/my-orders")
@login_required
def my_orders():
    orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("my_orders.html", orders=orders)


# ---------------------------------------------------------------------------
# Seller routes
# ---------------------------------------------------------------------------
@app.route("/seller/dashboard")
@role_required("seller")
def seller_dashboard():
    products = Product.query.filter_by(seller_id=current_user.id).order_by(Product.created_at.desc()).all()
    stats = {
        "total": len(products),
        "pending": sum(1 for p in products if p.status == "pending"),
        "approved": sum(1 for p in products if p.status == "approved"),
        "rejected": sum(1 for p in products if p.status == "rejected"),
    }
    return render_template("seller_dashboard.html", products=products, stats=stats)


@app.route("/seller/product/add", methods=["GET", "POST"])
@role_required("seller")
def seller_product_add():
    if request.method == "POST":
        name = request.form["name"].strip()
        description = request.form.get("description", "").strip()
        price = float(request.form["price"])
        stock = int(request.form["stock"])
        category = request.form.get("category", "General").strip() or "General"

        image_path = ""
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            image_path = f"uploads/{filename}"
        else:
            image_path = request.form.get("image_url", "").strip()

        product = Product(
            name=name, description=description, price=price, stock=stock,
            category=category, image=image_path, status="pending",
            seller_id=current_user.id,
        )
        db.session.add(product)
        db.session.commit()
        flash("Product submitted for admin approval.", "success")
        return redirect(url_for("seller_dashboard"))

    return render_template("seller_product_form.html", product=None)


@app.route("/seller/product/edit/<int:product_id>", methods=["GET", "POST"])
@role_required("seller")
def seller_product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    if product.seller_id != current_user.id:
        abort(403)

    if request.method == "POST":
        product.name = request.form["name"].strip()
        product.description = request.form.get("description", "").strip()
        product.price = float(request.form["price"])
        product.stock = int(request.form["stock"])
        product.category = request.form.get("category", "General").strip() or "General"

        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            product.image = f"uploads/{filename}"
        elif request.form.get("image_url", "").strip():
            product.image = request.form["image_url"].strip()

        # Edited product goes back to pending for re-approval
        product.status = "pending"
        db.session.commit()
        flash("Product updated and sent for re-approval.", "info")
        return redirect(url_for("seller_dashboard"))

    return render_template("seller_product_form.html", product=product)


@app.route("/seller/product/delete/<int:product_id>")
@role_required("seller")
def seller_product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    if product.seller_id != current_user.id:
        abort(403)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.", "info")
    return redirect(url_for("seller_dashboard"))


@app.route("/seller/orders")
@role_required("seller")
def seller_orders():
    items = (OrderItem.query.filter_by(seller_id=current_user.id)
             .join(Order).order_by(Order.created_at.desc()).all())
    return render_template("seller_orders.html", items=items, statuses=ORDER_STATUSES)


@app.route("/seller/order-item/<int:item_id>/status", methods=["POST"])
@role_required("seller")
def seller_order_item_status(item_id):
    item = OrderItem.query.get_or_404(item_id)
    if item.seller_id != current_user.id:
        abort(403)
    new_status = request.form.get("status")
    if new_status in ORDER_STATUSES:
        item.status = new_status
        db.session.commit()
        flash("Order status updated.", "success")
    return redirect(url_for("seller_orders"))


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------
@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    pending_products = Product.query.filter_by(status="pending").order_by(Product.created_at.desc()).all()
    stats = {
        "total_products": Product.query.count(),
        "pending": Product.query.filter_by(status="pending").count(),
        "approved": Product.query.filter_by(status="approved").count(),
        "sellers": User.query.filter_by(role="seller").count(),
        "customers": User.query.filter_by(role="customer").count(),
        "orders": Order.query.count(),
    }
    return render_template("admin_dashboard.html", pending_products=pending_products, stats=stats)


@app.route("/admin/products")
@role_required("admin")
def admin_products():
    status_filter = request.args.get("status", "")
    query = Product.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    products = query.order_by(Product.created_at.desc()).all()
    return render_template("admin_products.html", products=products, status_filter=status_filter)


@app.route("/admin/product/<int:product_id>/<action>")
@role_required("admin")
def admin_product_action(product_id, action):
    product = Product.query.get_or_404(product_id)
    if action == "approve":
        product.status = "approved"
        flash(f"{product.name} approved.", "success")
    elif action == "reject":
        product.status = "rejected"
        flash(f"{product.name} rejected.", "warning")
    db.session.commit()
    return redirect(request.referrer or url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Access forbidden."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


# ---------------------------------------------------------------------------
# DB init + seed data
# ---------------------------------------------------------------------------
def seed_data():
    if User.query.count() > 0:
        return

    admin = User(username="admin", email="admin@shopdesk.com", role="admin")
    admin.set_password("admin123")

    seller = User(username="rahul_seller", email="rahul@shopdesk.com", role="seller", shop_name="Rahul Electronics")
    seller.set_password("seller123")

    customer = User(username="priya", email="priya@shopdesk.com", role="customer")
    customer.set_password("customer123")

    db.session.add_all([admin, seller, customer])
    db.session.commit()

    def img(seed, w=500, h=400):
        return f"https://picsum.photos/seed/{seed}/{w}/{h}"

    supplements = [
        ("Whey Protein Powder (1kg)", "Premium whey protein isolate for fast muscle recovery. Chocolate flavor.", 2199, 40),
        ("Creatine Monohydrate (250g)", "Pure micronized creatine to boost strength and power output.", 899, 60),
        ("Mass Gainer (3kg)", "High-calorie mass gainer with protein and complex carbs for bulking.", 2799, 25),
        ("BCAA Powder (300g)", "Branched-chain amino acids to reduce muscle soreness and fatigue.", 1199, 45),
        ("Pre-Workout Formula (300g)", "Energy and focus booster for intense training sessions.", 1499, 35),
        ("Daily Multivitamin (60 tabs)", "Complete multivitamin support for active lifestyles.", 599, 70),
        ("Omega-3 Fish Oil (90 caps)", "Supports joint health and recovery with essential fatty acids.", 749, 55),
        ("L-Glutamine Powder (250g)", "Aids muscle recovery and supports gut health.", 999, 40),
        ("ZMA Recovery Capsules (90 caps)", "Zinc, magnesium and B6 for better sleep and recovery.", 849, 30),
        ("Protein Bars Box (12 bars)", "On-the-go protein bars, 20g protein per bar.", 1099, 50),
    ]

    bags = [
        ("Classic Gym Duffel Bag", "Spacious 40L duffel bag with separate shoe compartment.", 1299, 25),
        ("Gym Backpack 30L", "Durable backpack with laptop sleeve and shoe pocket.", 1599, 20),
        ("Waterproof Sports Bag", "Water-resistant fabric, ideal for daily gym commute.", 1099, 30),
        ("Gym Sling Bag", "Compact sling bag for phone, keys and small essentials.", 699, 40),
        ("Heavy Duty Travel Duffel", "Reinforced stitching, built for daily heavy use.", 1799, 15),
        ("Compact Gym Tote", "Lightweight tote bag, easy to carry, foldable design.", 849, 35),
        ("Gym Bag with Wet Pocket", "Separate wet pocket for shoes or sweaty clothes.", 1399, 20),
        ("Foldable Gym Bag", "Space-saving foldable design, packs flat when empty.", 749, 45),
        ("Premium Leather-Look Gym Bag", "Stylish design that works for gym and travel both.", 1999, 12),
        ("Kit Bag 25L", "Simple, affordable kit bag for everyday workouts.", 599, 50),
    ]

    shakers = [
        ("Classic Shaker Bottle 700ml", "BPA-free shaker with stainless steel mixing ball.", 349, 80),
        ("Steel Mixer Ball Shaker", "Extra smooth mixing with wire whisk ball technology.", 399, 70),
        ("Insulated Steel Shaker 500ml", "Double-wall insulation keeps drinks cold for hours.", 899, 30),
        ("3-Layer Storage Shaker", "Built-in compartments for pre/post workout supplements.", 549, 40),
        ("Leakproof Shaker Bottle", "100% leakproof screw lid, perfect for gym bags.", 379, 65),
        ("Electric Mixer Shaker", "Battery-powered mixer for perfectly smooth shakes.", 1299, 20),
        ("Sports Sipper Shaker 1L", "Large capacity sipper for all-day hydration.", 449, 55),
        ("BPA-Free Shaker 1L", "Extra-large 1 litre shaker for mass gainer shakes.", 499, 45),
        ("Gym Shaker with Compartment", "Side compartment for extra scoop of powder.", 599, 35),
        ("Premium Cyclone Shaker", "Cyclone mixing technology, zero clumps guaranteed.", 749, 25),
    ]

    vests = [
        ("Compression Gym Vest", "Muscle-fit compression vest for enhanced performance.", 649, 50),
        ("Classic Stringer Tank Top", "Bodybuilding stringer cut for maximum mobility.", 449, 60),
        ("Mesh Training Vest", "Breathable mesh fabric keeps you cool during workouts.", 549, 40),
        ("Sleeveless Muscle Vest", "Relaxed fit muscle vest for gym and casual wear.", 499, 55),
        ("Weighted Training Vest (10kg)", "Adjustable weighted vest for strength conditioning.", 2999, 10),
        ("Bodybuilding Tank Top", "Deep cut tank top designed for serious lifters.", 599, 35),
        ("Dri-Fit Sports Vest", "Moisture-wicking fabric, stays dry through intense sets.", 699, 45),
        ("Cotton Gym Vest", "Soft breathable cotton vest for everyday training.", 399, 65),
        ("Racerback Gym Vest", "Racerback design for unrestricted shoulder movement.", 549, 40),
        ("Sleeveless Hoodie Vest", "Hooded sleeveless vest, great for warm-ups.", 799, 20),
    ]

    category_map = {
        "Supplements": supplements,
        "Bags": bags,
        "Shakers": shakers,
        "Vests": vests,
    }

    sample_products = []
    for category, items in category_map.items():
        for idx, (name, desc, price, stock) in enumerate(items):
            seed = f"{category.lower()}-{idx}"
            sample_products.append(Product(
                name=name, description=desc, price=price, stock=stock,
                category=category, image=img(seed), status="approved", seller_id=seller.id,
            ))

    db.session.add_all(sample_products)
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_data()


if __name__ == "__main__":
    app.run(debug=True)
