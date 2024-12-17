import os

from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from pyzbar.pyzbar import decode
from PIL import Image
import bcrypt
import requests
import joblib
import pandas as pd
from datetime import datetime

from helpers import login_required

model = joblib.load('static/shelf_life_model.pkl')
le_food = joblib.load('static/item_encoder.pkl')
le_location = joblib.load('static/storage_encoder.pkl')
le_category = joblib.load('static/food_category_encoder.pkl')

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
    pantry_items = db.relationship('PantryItem', backref='user', lazy=True, cascade='all, delete-orphan')

class PantryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    image_path = db.Column(db.String(200), nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, default=None)
    location = db.Column(db.String(50), nullable=False) 

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    item_to_confirm = None
    file_path = None

    if request.method == 'POST':
        
        uploaded_file = request.files['image']
        
        if uploaded_file and uploaded_file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            filename = uploaded_file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            uploaded_file.save(file_path)

            try:
                # Try barcode detection
                image = Image.open(file_path)
                decoded_objects = decode(image)

                if decoded_objects:
                    barcode_data = decoded_objects[0].data.decode('utf-8')
                    response = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode_data}.json")
                    if response.status_code == 200:
                        product_info = response.json()
                        if product_info.get('product'):
                            item_to_confirm = product_info['product'].get('product_name', 'Unknown Product')

                # Fall back to object detection
                if not item_to_confirm:
                    url = "https://predict.ultralytics.com"
                    headers = {"x-api-key": "547b2e7f9c6af7c3fff3f3d6d6e13bd53dc2368fdb"}
                    data = {
                        "model": "https://hub.ultralytics.com/models/JNo67oJHwrmVSx8feV7c", 
                        "imgsz": 640,
                        "conf": 0.25,
                        "iou": 0.45
                    }

                    with open(file_path, "rb") as f:
                        response = requests.post(url, headers=headers, data=data, files={"file": f})
                    response.raise_for_status()
                    inference_results = response.json()

                    if inference_results.get("images"):
                        results = inference_results["images"][0].get("results", [])
                        if results:
                            top_prediction = results[0]
                            item_to_confirm = top_prediction.get("name")

                if not item_to_confirm:
                    flash("Could not recognize the contents of the image. Please manually enter the item name.", "warning")

            except Exception as e:
                flash(f"Error processing the image: {e}", "danger")
                return redirect('/')

    pantry_items = PantryItem.query.filter_by(user_id=session['user_id']).order_by(PantryItem.id.desc()).limit(6).all()
    pantry_ingredients = ",".join([item.name for item in pantry_items])

    try:
        response = requests.get(
            "https://api.spoonacular.com/recipes/findByIngredients",
            params={
                "ingredients": pantry_ingredients,
                "number": 6,
                "apiKey": "0e2a90d7b5514510ac91413e1d1a9669"
            }
        )
        recipes = response.json() if response.status_code == 200 else []
    except Exception as e:
        print(f"Error fetching recipes: {str(e)}")
        recipes = []

    return render_template(
        'index.html', 
        pantry_items=pantry_items, 
        recipes=recipes,
        item_to_confirm=item_to_confirm,
        file_path=file_path
    )


@app.route('/predict-expiry', methods=['POST'])
def predict_expiry():
    data = request.json
    item_name = data.get('item_name')
    storage_location = data.get('storage_location')
    food_category = data.get('food_category')  # Currently unused, can extend logic

    print("Raw inputs:", item_name, storage_location, food_category)  # Debug

    try:
        # Encode inputs
        item_encoded = le_food.transform([item_name])[0]
        location_encoded = le_location.transform([storage_location])[0]
        food_category_encoded = le_category.transform([food_category])[0]
        
        print("Encoded inputs:", item_encoded, location_encoded)  # Debug

        # Prepare data for the model
        input_data = pd.DataFrame([[item_encoded, location_encoded, food_category_encoded]],
                          columns=['Food Category Encoded', 'Storage Encoded', 'Item Encoded'])
        print("Model input:", input_data)  # Debug

        # Make prediction
        prediction = model.predict(input_data)
        print("Prediction result:", prediction)  # Debug
        
        return jsonify({"predicted_days": int(prediction[0])})
    except Exception as e:
        print("Error:", e)  # Debug
        return jsonify({"error": str(e)}), 400
    

@app.route('/add-item', methods=['POST'])
@login_required
def add_item():
    try:
        # Fetch form data
        item_name = request.form.get('name', '').strip()
        file_path = request.form.get('file_path')  # Optional image path
        expiry_date = request.form.get('expiry_date')  # Optional expiry date
        location = request.form.get('storage_location', '').strip()  # Added location field

        # Validate item name and location
        if not item_name or not location:
            flash("Item name and storage location are required.", "danger")
            return redirect('/')

        # Parse expiry date if provided
        parsed_expiry_date = None
        if expiry_date:
            try:
                parsed_expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid expiry date format. Please use YYYY-MM-DD.", "danger")
                return redirect('/')

        # Save the item to the database
        new_item = PantryItem(
            user_id=session['user_id'],
            name=item_name,
            image_path=file_path if file_path else None,  # Handle optional image path
            expiry_date=parsed_expiry_date,
            location=location  # Save storage location
        )
        db.session.add(new_item)
        db.session.commit()

        flash(f"Item '{item_name}' added to your {location.lower()} successfully!", "success")
    except Exception as e:
        flash(f"An error occurred while adding the item: {e}", "danger")
        return redirect('/')

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