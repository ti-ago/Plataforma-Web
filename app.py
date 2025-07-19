import os
import sqlite3
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Professional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstName = db.Column(db.String(150), nullable=False)
    lastName = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    contact_number = db.Column(db.String(150), nullable=False)
    hash = db.Column(db.String(150), nullable=False)

    @property
    def full_name(self):
        return f"{self.firstName} {self.lastName}"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstName = db.Column(db.String(150), nullable=False)
    lastName = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    document = db.Column(db.String(150), unique=True, nullable=False)
    hash = db.Column(db.String(150), nullable=False)

class UserData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('user_data', uselist=False))
    date_of_birth = db.Column(db.Date, nullable=True)
    contact_number = db.Column(db.String(150), nullable=True)
    height = db.Column(db.Float, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    gender = db.Column(db.String(150), nullable=True)
    address = db.Column(db.String(150), nullable=True)
    city = db.Column(db.String(150), nullable=True)
    state = db.Column(db.String(150), nullable=True)
    country = db.Column(db.String(150), nullable=True)
    payment_method = db.Column(db.String(150), nullable=True)
    points = db.Column(db.Integer, nullable=True)
    

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)

class UserSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    end_date = db.Column(db.DateTime, nullable=False)

    user = db.relationship('User', backref=db.backref('subscriptions', lazy=True))
    subscription = db.relationship('Subscription', backref=db.backref('user_subscriptions', lazy=True))

class Pictures(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_relationship = db.relationship('User', backref=db.backref('pictures', lazy=True))
    image = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(150), nullable=False)

class Appointment(db.Model):
    __tablename__ = 'appointment' # Boa prática definir o nome da tabela explicitamente
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False) # Ex: "Consulta de Nutrição Inicial"
    description = db.Column(db.String(500), nullable=True) # Notas do paciente ou do profissional
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='scheduled') # Ex: scheduled, completed, cancelled
    meeting_link = db.Column(db.String(255), nullable=True) # Para consultas online
    professional_id = db.Column(db.Integer, db.ForeignKey('professional.id'), nullable=False)
    professional = db.relationship('Professional', backref=db.backref('appointments', lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('appointments', lazy=True))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/register', methods=["GET", "POST"])
def register():
    
    if request.method == "POST":
        firstName = request.form.get("firstName")
        lastName = request.form.get("lastName")
        email = request.form.get("email")
        document = request.form.get("document")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        if password != confirmation:
            flash("Passwords do not match.", "error")
            return redirect(url_for('register'))
        
        hash = generate_password_hash(password, method='scrypt', salt_length=16)

        new_user = User(
            firstName=firstName,
            lastName=lastName,
            email=email,
            document=document,
            hash= hash
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash("An error occurred during registration.", "error")
            return render_template("register.html")
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template("register.html")
    

@app.route('/login', methods=["GET", "POST"])
def login():
    
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.hash, password):
            login_user(user)
            flash(f"Welcome back, {user.firstName}!", "info")
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password", "error")

    return render_template("login.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/contents')
@login_required
def contents():
    category = request.args.get('category')

    # Se nenhuma categoria for especificada na URL, redireciona para a página inicial.
    if not category:
        flash("Por favor, selecione uma categoria para ver os conteúdos.", "warning")
        return redirect(url_for('index'))

    # Mapeia os nomes das categorias para títulos mais amigáveis
    category_titles = {
        "physical_activity": "Atividade Física",
        "nutrition": "Nutrição",
        "emotional_care": "Cuidados Emocionais"
    }
    title = category_titles.get(category, "Conteúdos") # Usa "Conteúdos" como padrão

    video_file_path = os.path.join(app.root_path, 'data', 'videos.json')
    with open(video_file_path, 'r', encoding='utf-8') as f:
        all_videos = json.load(f)

    # Filtra os vídeos com base na categoria recebida pela URL
    videos_list = [video for video in all_videos if video['category'] == category]
    return render_template('contents.html', title=title, videos=videos_list)


@app.route('/forgot-password', methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        document = request.form.get("document")
        user = User.query.filter_by(email=email, document=document).first()
        
        if user:
            session['user_id'] = user.id
            return redirect(url_for('reset_password'))
        else:
            flash("User not found with the provided email and CPF.", "error")
            return redirect(url_for('forgot_password'))

    return render_template("forgot-password.html")

@app.route('/reset-password', methods=["GET", "POST"])
def reset_password():
    # TODO: This flow should be secured with a temporary token, not just a session.
    user_id = session.get('user_id')
    user = User.query.get(user_id)    
    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        if new_password == confirm_password:
            user.hash = generate_password_hash(new_password, method='scrypt', salt_length=16)
            db.session.commit()
            session.pop('user_id', None) # Clear the session
            flash("Your password has been reset successfully. Please log in.", "success")
            return redirect(url_for('login'))
        flash("Passwords do not match.", "error")
        return redirect(url_for('reset_password')) #
    return render_template("reset-password.html")

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route("/agenda", methods=["GET"])
@app.route("/agenda/<int:month>", methods=["GET"])
def agenda(month=None):
    months = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

    if month is None:
        month_selected = datetime.now().month - 1
    else:
        month_selected = month % 12

    mo = months[month_selected]

    return render_template("agenda.html", months=months, month_selected=month_selected, mo=mo)


if __name__ == '__main__':
    
    with app.app_context():
    
        db.create_all()
    
    app.run(debug=True)