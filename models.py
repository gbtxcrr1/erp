from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# ===================== USUÁRIOS (LOGIN) =====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    # controle de tentativas de login
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    @property
    def is_locked(self):
        """Indica se o usuário está bloqueado no momento."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def __repr__(self):
        return f"<Usuário {self.username}>"


# ===================== CLIENTES =====================
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(11), unique=True, nullable=False)
    phone = db.Column(db.String(12))
    email = db.Column(db.String(200), unique=True, nullable=False)
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(2))
    cep = db.Column(db.String(8))

    def __repr__(self):
        return f"<Cliente {self.name}>"


# ===================== PRODUTOS =====================
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(300))
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100))
    sku = db.Column(db.String(50), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Produto {self.name}>"


# ===================== ESTOQUE =====================
class StockItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    min_quantity = db.Column(db.Integer, default=0)
    location = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = db.relationship('Product', backref='stock_items')

    def __repr__(self):
        return f"<Estoque {self.product.name}>"


# ===================== VENDAS =====================
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship('Client', backref='sales')
    product = db.relationship('Product', backref='sales')

    def __repr__(self):
        return f"<Venda #{self.id}>"


# ===================== FINANCEIRO =====================
class FinancialTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # 'receita' ou 'despesa'
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<{self.type} {self.description}>"


# ===================== SUPORTE =====================
class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='aberto')  # aberto, em andamento, fechado
    priority = db.Column(db.String(20), nullable=False, default='média')  # baixa, média, alta
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = db.relationship('Client', backref='tickets')

    def __repr__(self):
        return f"<Chamado #{self.id} - {self.subject}>"


# ===================== FUNCIONÁRIOS =====================
class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(11), unique=True, nullable=False)
    position = db.Column(db.String(100))
    phone = db.Column(db.String(12))
    email = db.Column(db.String(200), unique=True)
    salary = db.Column(db.Float)
    hire_date = db.Column(db.Date)

    def __repr__(self):
        return f"<Funcionário {self.name}>"
