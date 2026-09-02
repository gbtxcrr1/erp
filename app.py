from functools import wraps
from flask import Flask, render_template
from flask import request, redirect, url_for, flash, session, g
from flask_migrate import Migrate
from datetime import datetime, timedelta

from config import Config
from models import (
    db, Client, Product, StockItem, Sale,
    FinancialTransaction, SupportTicket, Employee, User
)

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)


# ===================== CONTROLE DE ACESSO (LOGIN) =====================
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

        # login bem-sucedido: limpa tentativas e bloqueio
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
    return render_template("index.html")


# ===================== CLIENTES =====================
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


# ===================== PRODUTOS =====================
@app.route("/products")
@login_required
def products():
    products = Product.query.all()
    return render_template("products.html", products=products)


@app.route("/products/new", methods=["GET", "POST"])
@login_required
def new_product():
    if request.method == "POST":
        product = Product(
            name=request.form["name"],
            description=request.form["description"],
            price=float(request.form["price"] or 0),
            category=request.form["category"],
            sku=request.form["sku"],
        )
        db.session.add(product)
        db.session.flush()
        # cria um registro de estoque inicial se não existir
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
        product.name = request.form["name"]
        product.description = request.form["description"]
        product.price = float(request.form["price"] or 0)
        product.category = request.form["category"]
        product.sku = request.form["sku"]
        db.session.commit()
        flash("Produto atualizado!")
        return redirect(url_for("products"))
    return render_template("new_product.html", product=product)


@app.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    # remove registros de estoque relacionados
    StockItem.query.filter_by(product_id=product.id).delete()
    db.session.delete(product)
    db.session.commit()
    flash("Produto removido.")
    return redirect(url_for("products"))


# ===================== ESTOQUE =====================
@app.route("/stock")
@login_required
def stock():
    items = StockItem.query.all()
    return render_template("stock.html", items=items)


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
        item.quantity = int(request.form["quantity"])
        item.min_quantity = int(request.form["min_quantity"] or 0)
        item.location = request.form["location"]
        db.session.commit()
        flash("Estoque atualizado!")
        return redirect(url_for("stock"))
    return render_template("new_stock.html", products=Product.query.all(), item=item)


@app.route("/stock/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_stock(item_id):
    item = StockItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Registro de estoque removido.")
    return redirect(url_for("stock"))


# ===================== VENDAS =====================
@app.route("/sales")
@login_required
def sales():
    sales = Sale.query.order_by(Sale.date.desc()).all()
    return render_template("sales.html", sales=sales)


@app.route("/sales/new", methods=["GET", "POST"])
@login_required
def new_sale():
    clients = Client.query.all()
    products = Product.query.all()
    if request.method == "POST":
        product = Product.query.get(request.form["product_id"])
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


# ===================== FINANCEIRO =====================
@app.route("/finance")
@login_required
def finance():
    transactions = FinancialTransaction.query.order_by(FinancialTransaction.date.desc()).all()
    total_revenue = sum(t.amount for t in transactions if t.type == "receita")
    total_expense = sum(t.amount for t in transactions if t.type == "despesa")
    balance = total_revenue - total_expense
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


# ===================== SUPORTE =====================
@app.route("/support")
@login_required
def support():
    tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
    return render_template("support.html", tickets=tickets)


@app.route("/support/new", methods=["GET", "POST"])
@login_required
def new_ticket():
    clients = Client.query.all()
    if request.method == "POST":
        ticket = SupportTicket(
            client_id=request.form["client_id"],
            subject=request.form["subject"],
            description=request.form["description"],
            priority=request.form["priority"],
            status=request.form["status"],
        )
        db.session.add(ticket)
        db.session.commit()
        flash("Chamado aberto!")
        return redirect(url_for("support"))
    return render_template("new_ticket.html", clients=clients)


@app.route("/support/<int:ticket_id>/edit", methods=["GET", "POST"])
@login_required
def edit_ticket(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    if request.method == "POST":
        ticket.subject = request.form["subject"]
        ticket.description = request.form["description"]
        ticket.priority = request.form["priority"]
        ticket.status = request.form["status"]
        db.session.commit()
        flash("Chamado atualizado!")
        return redirect(url_for("support"))
    return render_template("new_ticket.html", clients=Client.query.all(), ticket=ticket)


@app.route("/support/<int:ticket_id>/delete", methods=["POST"])
@login_required
def delete_ticket(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    db.session.delete(ticket)
    db.session.commit()
    flash("Chamado removido.")
    return redirect(url_for("support"))


# ===================== FUNCIONÁRIOS =====================
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
