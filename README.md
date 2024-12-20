# Flask Application

This project is a Flask-based web application that includes features such as barcode scanning, food expiration prediction, and a user-friendly interface.

## Features
- Barcode scanning using `pyzbar`.
- Food ingredients prediction using the YOLOv5 model.
- Food expiration date prediction using a Random Forest regression model.
- Database integration with SQLAlchemy.
- User authentication with bcrypt.

---

## Prerequisites
Before running the application, ensure you have the following installed:
- Python 3.8 or later
- pip (Python package manager)
- Virtualenv or Conda (recommended)

---

## Setup Instructions

### 1. **Clone the Repository**  
   Clone this repository to your local machine and navigate into the project folder:
   ```bash
   git clone https://github.com/Jezter0/AI_AOL.git
   cd AI_AOL
   ```

### 2. **Set Up a Virtual Environment (Optional but Recommended)**  
   Create and activate a virtual environment:
   - On macOS/Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```

### 3. **Install Dependencies**  
   Install all required Python packages from `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

### 4. **Run the Flask Application**  
   Start the development server:
   ```bash
   flask run
   ```

---

## Access the Application

Once the server is running, open your web browser and navigate to:  
```
http://127.0.0.1:5000
```

You can now use the features of the application!

---

## Notes

- Ensure you have the necessary permissions and configurations if you're running the app on a remote server.
- If you encounter issues, ensure all dependencies are correctly installed or check your Python version compatibility.

---