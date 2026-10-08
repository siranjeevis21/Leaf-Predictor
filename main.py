import os
from flask import Flask, render_template, request ,redirect, url_for, session
import tensorflow as tf
from tensorflow.keras.models import load_model
import numpy as np
from PIL import Image
from authlib.integrations.flask_client import OAuth
import mysql.connector

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url=
    "https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="13579",
    database="mulberry_db"
)
cursor = db.cursor(dictionary=True)


model = tf.keras.models.load_model("Mulberry.keras")
class_names = [
    "01 ChiangMai60",
    "02 RedKing",
    "03 WhiteKing",
    "04 BlackOodTurkey",
    "05 TaiwanStraberry",
    "06 BlackAustralia",
    "07 Buriram60",
    "08 Kamphaengsaeng42",
    "09 TaiwanMeacho",
    "10 ChiangMaiBuriram60"
]

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/login")
def login():
    return google.authorize_redirect(
        url_for("callback", _external=True),
        prompt="select_account"
    )

@app.route("/login/callback")
def callback():

    token = google.authorize_access_token()

    user = token["userinfo"]

    google_id = user["sub"]
    name = user["name"]
    email = user["email"]
    picture = user["picture"]

    cursor.execute(
        """
        SELECT * FROM users
        WHERE email=%s
        """,
        (email,)
    )

    existing_user = cursor.fetchone()

    if not existing_user:

        cursor.execute(
            """
            INSERT INTO users(
                google_id,
                name,
                email,
                picture
            )
            VALUES(%s,%s,%s,%s)
            """,
            (
                google_id,
                name,
                email,
                picture
            )
        )

        db.commit()

        cursor.execute(
            """
            SELECT * FROM users
            WHERE email=%s
            """,
            (email,)
        )

        existing_user = cursor.fetchone()

    session["user"] = existing_user

    return redirect("/")


@app.route("/")
def home():
    if "user" not in session:
        return redirect("/auth")

    return render_template(
        "home.html",
        user=session["user"])

@app.route("/predict", methods=["POST"])
def predict():

    if "user" not in session:
        return redirect("/login")

    image = request.files["image"]

    image_path = os.path.join(
        UPLOAD_FOLDER,
        image.filename
    )

    image.save(image_path)

    img = Image.open(image_path)

    img = img.convert("RGB")

    img = img.resize((224, 224))

    img_array = np.array(img)

    img_array = img_array / 255.0

    img_array = np.expand_dims(
        img_array,
        axis=0
    )

    prediction = model.predict(img_array)

    predicted_index = np.argmax(prediction)

    confidence = float(
        np.max(prediction) * 100
    )

    predicted_class = class_names[
        predicted_index
    ]

    user_id = session["user"]["id"]

    cursor.execute(
        """
        INSERT INTO predictions(
            user_id,
            image_path,
            prediction,
            confidence
        )
        VALUES(%s,%s,%s,%s)
        """,
        (
            user_id,
            image_path,
            predicted_class,
            confidence
        )
    )

    db.commit()

    return render_template(
        "result.html",
        prediction=predicted_class,
        confidence=round(confidence, 2),
        image_path=image_path
    )

@app.route("/history")
def history():

    if "user" not in session:
        return redirect("/")

    user_id = session["user"]["id"]

    cursor.execute(
        """
        SELECT *
        FROM predictions
        WHERE user_id=%s
        ORDER BY created_at DESC
        """,
        (user_id,)
    )

    data = cursor.fetchall()

    return render_template(
        "history.html",
        data=data
    )

@app.route("/logout")
def logout():
    session.clear()
    return render_template("logged_out.html")

@app.route("/auth")
def auth():
    return render_template("auth.html")

if __name__ == "__main__":
    app.run(debug=True)

