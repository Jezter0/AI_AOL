import os

from flask import Flask, request, render_template, redirect, url_for, flash, session
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum, func
from clarifai.client.model import Model
from clarifai_grpc.grpc.api import resources_pb2, service_pb2, service_pb2_grpc
from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
import bcrypt
import requests
from datetime import datetime

from helpers import login_required

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///manager.db'
app.config['UPLOAD_FOLDER'] = './static/uploads'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    pantry_items = db.relationship('PantryItem', backref='user', lazy=True)

class PantryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    image_path = db.Column(db.String(200), nullable=False)
    expiry_date = db.Column(db.Date, nullable=True)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        uploaded_file = request.files['image']
        
        # Check if file was uploaded and has a valid extension
        if uploaded_file and uploaded_file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            # Generate a unique file name to avoid conflicts
            filename = uploaded_file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Save the uploaded file to the upload folder
            uploaded_file.save(file_path)

            # Use Clarifai to recognize the food item
            try:
                PAT = "ebd6c5aeea1d4656962de8aff353ffff"  # Your Clarifai API Key
                model_url = "https://clarifai.com/clarifai/main/models/food-item-recognition"

                model_prediction = Model(url=model_url, pat=PAT).predict_by_filepath(
                    file_path, input_type="image"
                )

                # Extract the predictions from the model response
                prediction_results = model_prediction.outputs[0].data.concepts

                # Get the top prediction (highest confidence)
                if prediction_results:
                    top_prediction = prediction_results[0]  # Get the highest confidence result
                    recognized_name = top_prediction.name

                    # Save to the database with current_user.id
                    new_item = PantryItem(
                        user_id=session['user_id'],  
                        name=recognized_name,
                        image_path=file_path,
                        expiry_date=datetime(2024, 12, 31)  
                    )
                    db.session.add(new_item)
                    db.session.commit()

            except Exception as e:
                return f"Error during AI prediction: {str(e)}", 500

    # Fetch pantry items for the current user from the database
    pantry_items = PantryItem.query.filter_by(user_id=session['user_id']).order_by(PantryItem.id.desc()).limit(4).all()
    pantry_ingredients = ",".join([item.name for item in pantry_items])

    try:
        response = requests.get(
            "https://api.spoonacular.com/recipes/findByIngredients",
            params={
                "ingredients": pantry_ingredients,
                "number": 5,  # Number of recipes to fetch
                "apiKey": "0e2a90d7b5514510ac91413e1d1a9669"
            }
        )
        recipes = response.json() if response.status_code == 200 else []

    except Exception as e:
        print(f"Error fetching recipes: {str(e)}")
        recipes = []

    # Render the template and pass the pantry items for display
    return render_template('index.html', pantry_items=pantry_items, recipes=recipes)


@app.route('/pantry', methods=['GET', 'POST'])
@login_required
def pantry():
    pantry_items = PantryItem.query.filter_by(user_id=session['user_id'])

    return render_template('pantry.html', pantry_items=pantry_items)


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
    

@login_required
@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()

    return redirect("/")



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run()