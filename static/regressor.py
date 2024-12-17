import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
import matplotlib.pyplot as plt

# Step 1: Load and preprocess the data
# Read the CSV file
df = pd.read_csv('data_normal.csv')

# Create separate encoders for each categorical column
food_category_encoder = LabelEncoder()
storage_encoder = LabelEncoder()
item_encoder = LabelEncoder()

# Encode the columns
df['Food Category Encoded'] = food_category_encoder.fit_transform(df['Food Category'])
df['Storage Encoded'] = storage_encoder.fit_transform(df['Storage'])
df['Item Encoded'] = item_encoder.fit_transform(df['Item'])

# Features and target
X = df[['Food Category Encoded', 'Storage Encoded', 'Item Encoded']]  # Features
y = df['Shelf Life (in Days)']  # Target

# Step 2: Split the data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Step 3: Create and train the Random Forest Regressor model
regressor = RandomForestRegressor(random_state=42, n_estimators=100)
regressor.fit(X_train, y_train)

# Step 4: Evaluate the model
score = regressor.score(X_test, y_test)
y_pred = regressor.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))

print(f'MAE: {mae:.2f}')
print(f'RMSE: {rmse:.2f}')
print(f'R-squared score: {score:.4f}')

# Example of two-word item name
item_name = 'Sponge Gourd -Ghiraula-'
storage_location = 'Fridge'  # Just an example
food_category = 'Root Vegetables'  # Example category

# Encoding the two-word item name and other input data
item_encoded = item_encoder.transform([item_name])[0]  # Transform the item_name to encoded value
food_category_encoded = food_category_encoder.transform([food_category])[0]
storage_encoded = storage_encoder.transform([storage_location])[0]

# Creating a feature array with encoded values
X_input = np.array([[food_category_encoded, storage_encoded, item_encoded]])

# Predicting shelf life (in days) using the trained model
predicted_shelf_life = regressor.predict(X_input)
print(f'Predicted shelf life for "{item_name}": {predicted_shelf_life[0]:.2f} days')

# # Step 5: Feature importance visualization
# importances = regressor.feature_importances_
# feature_names = ['Food Category', 'Storage', 'Item']
# plt.bar(feature_names, importances, color='skyblue')
# plt.title('Feature Importance')
# plt.xlabel('Features')
# plt.ylabel('Importance')
# plt.show()

# Save the trained model
joblib.dump(regressor, 'shelf_life_model.pkl')

# Save the encoders
joblib.dump(food_category_encoder, 'food_category_encoder.pkl')
joblib.dump(storage_encoder, 'storage_encoder.pkl')
joblib.dump(item_encoder, 'item_encoder.pkl')