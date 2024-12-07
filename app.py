import os

from flask import Flask, request, render_template, redirect, url_for, flash, session
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from inference_sdk import InferenceHTTPClient
from pyzbar.pyzbar import decode
from PIL import Image
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
    item_to_confirm = None
    file_path = None

    if request.method == 'POST':
        uploaded_file = request.files['image']
        
        # Check if file was uploaded and has a valid extension
        if uploaded_file and uploaded_file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            # Generate a unique file name to avoid conflicts
            filename = uploaded_file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Save the uploaded file to the upload folder
            uploaded_file.save(file_path)

            # Initialize the Roboflow client
            client = InferenceHTTPClient(
                api_url="https://detect.roboflow.com", 
                api_key="ppadgygy71nMH5zcUypQ"
            )

            try:
                # Try barcode detection
                image = Image.open(file_path)
                decoded_objects = decode(image)

                if decoded_objects:
                    # Use the first barcode found
                    barcode_data = decoded_objects[0].data.decode('utf-8')
                    print(f"Detected Barcode: {barcode_data}")

                    # Query Open Food Facts API with the barcode
                    response = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode_data}.json")
                    if response.status_code == 200:
                        product_info = response.json()
                        if product_info.get('product'):
                            item_to_confirm = product_info['product'].get('product_name', 'Unknown Product')

                # If barcode detection fails, fall back to Roboflow
                if not item_to_confirm:
                    result = client.infer(file_path, model_id="food-ingredients-dataset/3")
                    if result.get('predictions'):
                        top_prediction = result['predictions'][0]
                        item_to_confirm = top_prediction['class']  # Class name of the prediction
            except Exception as e:
                flash(f"Error processing the image: {e}", "danger")
                return redirect('/')

    # Fetch pantry items for the current user from the database
    pantry_items = PantryItem.query.filter_by(user_id=session['user_id']).order_by(PantryItem.id.desc()).limit(6).all()
    pantry_ingredients = ",".join([item.name for item in pantry_items])

    try:
        response = requests.get(
            "https://api.spoonacular.com/recipes/findByIngredients",
            params={
                "ingredients": pantry_ingredients,
                "number": 6,  # Number of recipes to fetch
                "apiKey": "0e2a90d7b5514510ac91413e1d1a9669"
            }
        )
        recipes = response.json() if response.status_code == 200 else []

    except Exception as e:
        print(f"Error fetching recipes: {str(e)}")
        recipes = []

    # Render the template with confirmation form data
    return render_template(
        'index.html', 
        pantry_items=pantry_items, 
        recipes=recipes,
        item_to_confirm=item_to_confirm,
        file_path=file_path
    )


@app.route('/add-item', methods=['POST'])
@login_required
def add_item():
    # Fetch form data
    item_name = request.form.get('name')
    file_path = request.form.get('file_path')
    expiry_date = request.form.get('expiry_date')

    # Save the item to the database
    new_item = PantryItem(
        user_id=session['user_id'],
        name=item_name,
        image_path=file_path,
        expiry_date=datetime.strptime(expiry_date, "%Y-%m-%d") if expiry_date else None
    )
    db.session.add(new_item)
    db.session.commit()
    flash(f"Item '{item_name}' added successfully!", "success")
    return redirect('/')

@app.route('/pantry', methods=['GET', 'POST'])
@login_required
def pantry():
    pantry_items = PantryItem.query.filter_by(user_id=session['user_id'])

    return render_template('pantry.html', pantry_items=pantry_items)


@app.route('/pantry/<int:item_id>', methods=['DELETE'])
@login_required
def delete_pantry_item(item_id):
    # Find the item to delete
    item = PantryItem.query.filter_by(id=item_id, user_id=session['user_id']).first()
    if not item:
        return {"error": "Item not found or unauthorized"}, 404

    # Delete the item
    db.session.delete(item)
    db.session.commit()
    return {"message": "Item deleted successfully"}, 200


@app.route('/recommendation', methods=['GET'])
@login_required
def recommendation():
    pantry_items = PantryItem.query.filter_by(user_id=session['user_id'])
    pantry_ingredients = ",".join([item.name for item in pantry_items])

    try:
        response = requests.get(
            "https://api.spoonacular.com/recipes/findByIngredients",
            params={
                "ingredients": pantry_ingredients,
                "number": 50,  # Number of recipes to fetch
                "apiKey": "0e2a90d7b5514510ac91413e1d1a9669"
            }
        )
        recipes = response.json() if response.status_code == 200 else []

    except Exception as e:
        print(f"Error fetching recipes: {str(e)}")
        recipes = []

    return render_template('recommendation.html', recipes=recipes)


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