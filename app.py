import os

from flask import Flask, request, render_template, redirect, url_for, flash, session
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum, func
import bcrypt

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///manager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run()