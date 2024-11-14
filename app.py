import os

from flask import Flask, request, render_template, redirect, url_for, flash, session
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum, func
import bcrypt

from helpers import login_required

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///manager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        confirm = request.form['confirmation'].encode('utf-8')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        elif confirm != password:
            flash('Password and Confirmation do not match', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
        
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        user = User.query.filter_by(username=username).first()
        session["user_id"] = user.id
        
        return redirect("/")
    else:
        return render_template('register.html')
    

@app.route('/login', methods=['GET', 'POST'])
def login():

    session.clear()

    if request.method == 'POST':
        if not request.form.get("username"):
            return render_template('login.html')
        elif not request.form.get("password"):
            return render_template("login.html")

        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password, user.password):
            session["user_id"] = user.id
            return redirect("/")
        else:
            return redirect(url_for("login"))
    else:
        return render_template('login.html')
    
    
@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()

    return redirect("/")



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run()