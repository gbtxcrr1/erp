from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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