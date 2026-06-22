from flask import Flask, render_template

from config import Config
from models import db

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/clients")
def clients():
    return render_template("clients.html")

@app.route("/products")
def products():
    return render_template("products.html")

if __name__ == "__main__":
    app.run(debug=True)