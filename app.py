import re
from functools import wraps
from flask import Flask, render_template
from flask import request, redirect, url_for, flash, session, g
from flask_migrate import Migrate
from sqlalchemy import func
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from translations import MOVEMENT_TYPES, MOVEMENT_DIRECTIONS

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
UTC = ZoneInfo("UTC")

from config import Config
from models import (
    db, Client, Product, StockItem, StockMovement, Sale, Purchase,
    FinancialTransaction, Employee, User
)

app = Flask(__name__)
app.config.from_object(Config)

@app.template_filter("brl")
def brl(value):
    try:
        value = round(float(value or 0), 2)
    except (TypeError, ValueError):
        value = 0.0
    formatted = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sign = "-" if value < 0 else ""
    return f"{sign}R$ {formatted}"

db.init_app(app)
migrate = Migrate(app, db)


# ===================== LOGIN =====================
def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = db.session.get(User, user_id)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        # usuário bloqueado? (apos 3 tentativas, espera 1 minuto)
        if user and user.locked_until and datetime.utcnow() < user.locked_until:
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds())
            flash(f"Conta temporariamente bloqueada. Tente novamente em {remaining} segundo(s).")
            return render_template("login.html")

        if user is None or not user.check_password(password):
            if user is not None:
                user.failed_attempts = (user.failed_attempts or 0) + 1
                if user.failed_attempts >= app.config["MAX_LOGIN_ATTEMPTS"]:
                    user.locked_until = datetime.utcnow() + timedelta(
                        seconds=app.config["LOGIN_LOCK_SECONDS"]
                    )
                    user.failed_attempts = 0
                    db.session.commit()
                    flash("Senha incorreta. Conta bloqueada por 1 minuto por excesso de tentativas.")
                else:
                    db.session.commit()
                    tentativas = user.failed_attempts
                    restantes = app.config["MAX_LOGIN_ATTEMPTS"] - tentativas
                    flash(f"Usuário ou senha incorretos. Tentativa {tentativas} de {app.config['MAX_LOGIN_ATTEMPTS']}. {restantes} tentativa(s) restante(s).")
            else:
                flash("Usuário ou senha incorretos.")
            return render_template("login.html")

        user.failed_attempts = 0
        user.locked_until = None
        db.session.commit()

        session.clear()
        session["user_id"] = user.id
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    total_revenue = db.session.query(
        func.sum(FinancialTransaction.amount)
    ).filter_by(type="receita").scalar() or 0

    total_expense = db.session.query(
        func.sum(FinancialTransaction.amount)
    ).filter_by(type="despesa").scalar() or 0

    balance = total_revenue - total_expense
    total_products = Product.query.count()


    # Monthly financial data
    month_names = [
        "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez"
    ]

    now = datetime.utcnow()
    months = {}

    for offset in range(5, -1, -1):
        month_index = now.month - offset
        year = now.year

        while month_index <= 0:
            month_index += 12
            year -= 1

        key = f"{year}-{month_index:02d}"

        months[key] = {
            "month": month_names[month_index - 1],
            "revenue": 0,
            "expenses": 0
        }

    monthly_data = db.session.query(
        func.strftime("%Y-%m", FinancialTransaction.date).label("month"),
        FinancialTransaction.type,
        func.sum(FinancialTransaction.amount).label("total")
    ).group_by(
        "month",
        FinancialTransaction.type
    ).all()

    for month, transaction_type, total in monthly_data:
        if month in months:
            if transaction_type == "receita":
                months[month]["revenue"] = float(total)
            elif transaction_type == "despesa":
                months[month]["expenses"] = float(total)

    chart_data = list(months.values())

    return render_template(
        "index.html",
        total_revenue=total_revenue,
        total_expense=total_expense,
        balance=balance,
        total_products=total_products,
        chart_data=chart_data
    )



# ===================== CLIENTS =====================
@app.route("/clients")
@login_required
def clients():
    clients = Client.query.all()
    return render_template("clients.html", clients=clients)


@app.route("/clients/new", methods=["GET", "POST"])
@login_required
def new_client():
    if request.method == "POST":
        client = Client(
            name=request.form["name"],
            cpf=request.form["cpf"],
            phone=request.form["phone"],
            email=request.form["email"],
            address=request.form["address"],
            city=request.form["city"],
            state=request.form["state"],
            cep=request.form["cep"],
        )
        db.session.add(client)
        db.session.commit()
        flash("Cliente cadastrado com sucesso!")
        return redirect(url_for("clients"))
    return render_template("new_client.html")


@app.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == "POST":
        client.name = request.form["name"]
        client.cpf = request.form["cpf"]
        client.phone = request.form["phone"]
        client.email = request.form["email"]
        client.address = request.form["address"]
        client.city = request.form["city"]
        client.state = request.form["state"]
        client.cep = request.form["cep"]
        db.session.commit()
        flash("Cliente atualizado com sucesso!")
        return redirect(url_for("clients"))
    return render_template("new_client.html", client=client)


@app.route("/clients/<int:client_id>/delete", methods=["POST"])
@login_required
def delete_client(client_id):
    client = Client.query.get_or_404(client_id)
    db.session.delete(client)
    db.session.commit()
    flash("Cliente removido.")
    return redirect(url_for("clients"))


SKU_PREFIXES = {
    "Smartphones": "CELS",
    "Computadores": "COMP",
    "Tablets": "TABS",
    "Periféricos": "PERF",
    "Componentes": "PECA",
    "Monitores": "TELA",
    "Áudio": "SONS",
    "Acessórios": "FONE",
    "Redes": "CPLP",
    "Armazenamento": "ARMS",
    "Outros": "OUTR",
}


def generate_sku(category):
    prefix = SKU_PREFIXES.get(category, "OUTR")
    pattern = re.compile(rf"^{prefix}(\d{{4}})([A-Z])$")

    last = 0
    for (sku,) in db.session.query(Product.sku).filter(Product.sku.like(f"{prefix}_____")):
        match = pattern.match(sku or "")
        if match:
            seq = (ord(match.group(2)) - 65) * 9999 + int(match.group(1))
            last = max(last, seq)

    block, digits = divmod(last, 9999)
    return f"{prefix}{digits + 1:04d}{chr(65 + block)}"


# ===================== PRODUCTS =====================
@app.route("/products")
@login_required
def products():
    products = Product.query.filter_by(active=True).all()

    products_with_history = set()

    for product in products:
        has_purchases = Purchase.query.filter_by(product_id=product.id).first()
        has_movements = StockMovement.query.filter_by(product_id=product.id).first()

        if has_purchases or has_movements:
            products_with_history.add(product.id)

    return render_template(
        "products.html",
        products=products,
        products_with_history=products_with_history
    )

@app.route("/products/inactive")
@login_required
def inactive_products():
    products = Product.query.filter_by(active=False).all()
    return render_template("inactive_products.html", products=products)


@app.route("/products/<int:product_id>/reactivate", methods=["POST"])
@login_required
def reactivate_product(product_id):
    product = Product.query.get_or_404(product_id)

    product.active = True
    db.session.commit()

    flash("Produto reativado com sucesso!")
    return redirect(url_for("inactive_products"))


@app.route("/products/new", methods=["GET", "POST"])
@login_required
def new_product():
    if request.method == "POST":
        price = float(request.form["price"] or 0)

        if price < 0:
            flash("O preço não pode ser negativo.")
            return render_template("new_product.html")

        product = Product(
            name=request.form["name"],
            description=request.form["description"],
            price=price,
            category=request.form["category"],
            sku=generate_sku(request.form["category"]),
        )

        db.session.add(product)
        db.session.flush()

        if not StockItem.query.filter_by(product_id=product.id).first():
            db.session.add(StockItem(product_id=product.id, quantity=0, location="Geral"))

        db.session.commit()
        flash("Produto cadastrado com sucesso!")
        return redirect(url_for("products"))

    return render_template("new_product.html")


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        price = float(request.form["price"] or 0)

        if price < 0:
            flash("O preço não pode ser negativo.")
            return render_template("new_product.html", product=product)

        product.name = request.form["name"]
        product.description = request.form["description"]
        product.price = price
        product.category = request.form["category"]

        db.session.commit()
        flash("Produto atualizado!")
        return redirect(url_for("products"))

    return render_template("new_product.html", product=product)


@app.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)

    has_purchases = Purchase.query.filter_by(product_id=product.id).first()
    has_movements = StockMovement.query.filter_by(product_id=product.id).first()

    if has_purchases or has_movements:
        product.active = False
        db.session.commit()
        flash("Produto desativado com sucesso!")
    else:
        StockItem.query.filter_by(product_id=product.id).delete()
        db.session.delete(product)
        db.session.commit()
        flash("Produto removido com sucesso!")

    return redirect(url_for("products"))

# ===================== STOCK =====================
@app.route("/stock")
@login_required
def stock():
    items = StockItem.query.all()
    movements = StockMovement.query.order_by(StockMovement.date.desc()).all()
    for movement in movements:
        if movement.date:
            movement.date = movement.date.replace(tzinfo=UTC).astimezone(BRAZIL_TZ)
    return render_template(
        "stock.html",
        items=items, 
        movements=movements, 
        movement_types=MOVEMENT_TYPES,
        movement_directions=MOVEMENT_DIRECTIONS
    )


@app.route("/stock/new", methods=["GET", "POST"])
@login_required
def new_stock():
    products = Product.query.all()
    if request.method == "POST":
        product_id = request.form["product_id"]
        # se já existe, atualiza quantidade em vez de duplicar
        item = StockItem.query.filter_by(product_id=product_id).first()
        if item:
            item.quantity += int(request.form["quantity"])
        else:
            item = StockItem(
                product_id=product_id,
                quantity=int(request.form["quantity"]),
                min_quantity=int(request.form["min_quantity"] or 0),
                location=request.form["location"],
            )
            db.session.add(item)
        db.session.commit()
        flash("Estoque atualizado!")
        return redirect(url_for("stock"))
    return render_template("new_stock.html", products=products)




@app.route("/stock/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_stock(item_id):
    item = StockItem.query.get_or_404(item_id)

    if request.method == "POST":
        old_quantity = item.quantity

        try:
            new_quantity = int(request.form["quantity"])
            min_quantity = int(request.form["min_quantity"] or 0)
        except ValueError:
            flash("Informe quantidades válidas.")
            return render_template(
                "new_stock.html",
                products=Product.query.all(),
                item=item
            )

        if new_quantity < 0 or min_quantity < 0:
            flash("As quantidades não podem ser negativas.")
            return render_template(
                "new_stock.html",
                products=Product.query.all(),
                item=item
            )

        if old_quantity != new_quantity:
            movement = StockMovement(
                product_id=item.product_id,
                user_id=g.user.id,
                movement_type="adjustment",
                direction="in" if new_quantity > old_quantity else "out",
                quantity=abs(new_quantity - old_quantity)
            )
            db.session.add(movement)

        item.quantity = new_quantity
        item.min_quantity = min_quantity
        item.location = request.form["location"]

        db.session.commit()
        flash("Estoque atualizado!")
        return redirect(url_for("stock"))

    return render_template(
        "new_stock.html",
        products=Product.query.all(),
        item=item
    )



@app.route("/stock/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_stock(item_id):
    item = StockItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Registro de estoque removido.")
    return redirect(url_for("stock"))


# ===================== SALES =====================
@app.route("/sales")
@login_required
def sales():
    sales = Sale.query.order_by(Sale.date.desc()).all()
    for sale in sales:
        sale.date = sale.date.replace(tzinfo=UTC).astimezone(BRAZIL_TZ)
    return render_template("sales.html", sales=sales)


@app.route("/sales/new", methods=["GET", "POST"])
@login_required
def new_sale():
    clients = Client.query.all()
    products = Product.query.filter_by(active=True).all()
    if request.method == "POST":
        product = Product.query.get(request.form["product_id"])
        
        if product is None or not product.active:
            flash("Este produto está inativo ou não existe.")
            return render_template("new_sale.html", clients=clients, products=products)
        quantity = int(request.form["quantity"])

        # verifica estoque
        stock = StockItem.query.filter_by(product_id=product.id).first()
        if stock and stock.quantity >= quantity:
            stock.quantity -= quantity
        elif stock is None:
            flash("Este produto não possui registro de estoque.")
            return render_template("new_sale.html", clients=clients, products=products)
        else:
            flash(f"Estoque insuficiente (disponível: {stock.quantity}).")
            return render_template("new_sale.html", clients=clients, products=products)

        movement = StockMovement(
            product_id=product.id,
            employee_id=None,
            user_id=g.user.id,
            movement_type='sale',
            direction='out',
            quantity=quantity,
            reason=None
        )

        db.session.add(movement)

        total = product.price * quantity
        sale = Sale(
            client_id=request.form["client_id"],
            product_id=product.id,
            quantity=quantity,
            unit_price=product.price,
            total_price=total,
        )
        db.session.add(sale)

        client = Client.query.get(request.form["client_id"])
        client_name = client.name if client else f"ID #{request.form['client_id']}"

        finance_input = FinancialTransaction(
            type="receita",                                                 # Mapeia seu campo 'type'
            description=f"{product.name} vendido para {client_name}",     # Mapeia seu campo 'description'
            amount=total,                                                   # Mapeia seu campo 'amount' (Float)
            category=product.category,                                              # Mapeia seu campo 'category'
            # O campo 'date' não precisa enviar, ele usa o default=datetime.utcnow automaticamente!
        )
        
        # 3. Adiciona na sessão para salvar junto com a venda no commit seguinte
        db.session.add(finance_input)

        db.session.commit()
        flash("Venda registrada!")
        return redirect(url_for("sales"))
    return render_template("new_sale.html", clients=clients, products=products)


@app.route("/sales/<int:sale_id>/delete", methods=["POST"])
@login_required
def delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    db.session.delete(sale)
    db.session.commit()
    flash("Venda removida.")
    return redirect(url_for("sales"))



# ===================== PURCHASES =====================

@app.route("/purchases")
@login_required
def purchase_list():
    purchases = Purchase.query.order_by(
        Purchase.date.desc()
    ).all()

    for purchase in purchases:
        purchase.date = purchase.date.replace(tzinfo=UTC).astimezone(BRAZIL_TZ)

    total_purchases = sum(
        purchase.total_price or 0
        for purchase in purchases
    )

    return render_template(
        "purchases.html",
        purchases=purchases,
        total_purchases=total_purchases
    )

@app.route("/purchases/new", methods=["GET", "POST"])
@login_required
def new_purchase():
    products = Product.query.filter_by(active=True).all()

    if request.method == "POST":
        product = Product.query.get(request.form["product_id"])
        
        if product is None or not product.active:
            flash("Este produto está inativo ou não existe.")
            return render_template("new_purchase.html", products=products)
        quantity = int(request.form["quantity"])
        unit_price = float(request.form["unit_price"])

        if product is None:
            flash("Produto não encontrado.")
            return render_template("new_purchase.html", products=products)

        if quantity <= 0 or unit_price <= 0:
            flash("Quantidade e preço devem ser maiores que zero.")
            return render_template("new_purchase.html", products=products)

        total = quantity * unit_price

        # Atualiza estoque
        stock = StockItem.query.filter_by(product_id=product.id).first()

        if stock:
            stock.quantity += quantity
        else:
            stock = StockItem(
                product_id=product.id,
                quantity=quantity,
                min_quantity=0
            )
            db.session.add(stock)

        # Registra compra
        purchase = Purchase(
            product_id=product.id,
            user_id=g.user.id,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total
        )
        db.session.add(purchase)

        # Registra movimentação de estoque
        movement = StockMovement(
            product_id=product.id,
            user_id=g.user.id,
            movement_type="purchase",
            direction="in",
            quantity=quantity
        )
        db.session.add(movement)

        # Registra despesa financeira
        finance_input = FinancialTransaction(
            type="despesa",
            description=f"Compra de {quantity} unidade(s) de {product.name}",
            amount=total,
            category=product.category
        )
        db.session.add(finance_input)

        db.session.commit()

        flash("Compra registrada com sucesso!")
        return redirect(url_for("purchase_list"))

    return render_template("new_purchase.html", products=products)



# ===================== FINANCE =====================
@app.route("/finance")
@login_required
def finance():
    transactions = FinancialTransaction.query.order_by(FinancialTransaction.date.desc()).all()
    total_revenue = sum(t.amount for t in transactions if t.type == "receita")
    total_expense = sum(t.amount for t in transactions if t.type == "despesa")
    balance = total_revenue - total_expense
    for transaction in transactions:
        transaction.date = transaction.date.replace(tzinfo=UTC).astimezone(BRAZIL_TZ)
    return render_template(
        "finance.html",
        transactions=transactions,
        total_revenue=total_revenue,
        total_expense=total_expense,
        balance=balance,
    )


@app.route("/finance/new", methods=["GET", "POST"])
@login_required
def new_transaction():
    if request.method == "POST":
        transaction = FinancialTransaction(
            type=request.form["type"],
            description=request.form["description"],
            amount=float(request.form["amount"] or 0),
            category=request.form["category"],
        )
        db.session.add(transaction)
        db.session.commit()
        flash("Lançamento registrado!")
        return redirect(url_for("finance"))
    return render_template("new_transaction.html")


@app.route("/finance/<int:transaction_id>/delete", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    transaction = FinancialTransaction.query.get_or_404(transaction_id)
    db.session.delete(transaction)
    db.session.commit()
    flash("Lançamento removido.")
    return redirect(url_for("finance"))

# ===================== EMPLOYEES =====================
@app.route("/employees")
@login_required
def employees():
    employees = Employee.query.all()
    return render_template("employees.html", employees=employees)


@app.route("/employees/new", methods=["GET", "POST"])
@login_required
def new_employee():
    if request.method == "POST":
        hire_date = None
        if request.form["hire_date"]:
            hire_date = datetime.strptime(request.form["hire_date"], "%Y-%m-%d").date()
        employee = Employee(
            name=request.form["name"],
            cpf=request.form["cpf"],
            position=request.form["position"],
            phone=request.form["phone"],
            email=request.form["email"],
            salary=float(request.form["salary"] or 0),
            hire_date=hire_date,
        )
        db.session.add(employee)
        db.session.commit()
        flash("Funcionário cadastrado!")
        return redirect(url_for("employees"))
    return render_template("new_employee.html")


@app.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
def edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    if request.method == "POST":
        hire_date = None
        if request.form["hire_date"]:
            hire_date = datetime.strptime(request.form["hire_date"], "%Y-%m-%d").date()
        employee.name = request.form["name"]
        employee.cpf = request.form["cpf"]
        employee.position = request.form["position"]
        employee.phone = request.form["phone"]
        employee.email = request.form["email"]
        employee.salary = float(request.form["salary"] or 0)
        employee.hire_date = hire_date
        db.session.commit()
        flash("Funcionário atualizado!")
        return redirect(url_for("employees"))
    return render_template("new_employee.html", employee=employee)


@app.route("/employees/<int:employee_id>/delete", methods=["POST"])
@login_required
def delete_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    db.session.delete(employee)
    db.session.commit()
    flash("Funcionário removido.")
    return redirect(url_for("employees"))


if __name__ == "__main__":
    app.run(debug=True)
