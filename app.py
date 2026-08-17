from flask import Flask, render_template
from flask import request, redirect, url_for
from flask_migrate import Migrate

from config import Config
from models import db, Client

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# after adding new columns
migrate = Migrate(app, db)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/clients")
def clients():
    clients = Client.query.all()
    return render_template("clients.html", clients=clients)

@app.route("/clients/new", methods=["GET", "POST"])
def new_client():
    if request.method == "POST":
        name = request.form["name"]
        cpf = request.form["cpf"]
        phone = request.form["phone"]
        email = request.form["email"]
        address = request.form["address"]
        city = request.form["city"]
        state = request.form["state"]
        cep = request.form["cep"]

        new_client = Client(
            name=name,
            cpf=cpf,
            phone=phone,
            email=email,
            address=address,
            city=city,
            state=state,
            cep=cep
        )

        db.session.add(new_client)
        db.session.commit()

        return redirect(url_for("clients"))

    return render_template("new_client.html")

@app.route("/products")
def products():
    return render_template("products.html")

@app.route("/sales")
def sales():
    return render_template("sales.html")

@app.route("/stock")
def stock():
    return render_template("stock.html")

@app.route("/finance")
def finance():
    return render_template("finance.html")

@app.route("/support")
def support():
    return render_template("support.html")

@app.route("/employees")
def employees():
    return render_template("employees.html")

if __name__ == "__main__":
    app.run(debug=True)