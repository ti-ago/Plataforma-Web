import os
import calendar
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, time
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

# Tabela de associação para a relação N-N (Muitos-para-Muitos)
# entre Profissionais e Áreas.
professional_areas = db.Table('professional_areas',
    db.Column('professional_id', db.Integer, db.ForeignKey('professional.id'), primary_key=True),
    db.Column('area_id', db.Integer, db.ForeignKey('area.id'), primary_key=True)
)

class Area(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False) # e.g., Nutrição, Atividade Física
    # A relação agora usa a tabela de associação 'professional_areas'
    professionals = db.relationship('Professional', secondary=professional_areas, back_populates='areas', lazy='dynamic')

    def __repr__(self):
        return f'<Area {self.name}>'

class Professional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstName = db.Column(db.String(150), nullable=False)
    lastName = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    contact_number = db.Column(db.String(150), nullable=False)
    hash = db.Column(db.String(150), nullable=False)
    areas = db.relationship('Area', secondary=professional_areas, back_populates='professionals', lazy='dynamic')

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

    @property
    def has_active_subscription(self):
        """Verifica se o usuário tem uma assinatura ativa de forma eficiente."""
        return UserSubscription.query.filter(UserSubscription.user_id == self.id, 
                                             UserSubscription.end_date > datetime.now()).first() is not None

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

    if not category:
        flash("Por favor, selecione uma categoria para ver os conteúdos.", "warning")
        return redirect(url_for('index'))

    
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
            session.pop('user_id', None)
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

@app.route('/professionals')
@login_required
def professionals():
    """Exibe uma lista de todos os profissionais e suas áreas."""

    all_professionals = Professional.query.join(Area).order_by(Area.name, Professional.lastName).all()
    return render_template('professionals.html', professionals=all_professionals)

@app.route('/subscriptions')
@login_required
def subscriptions_page():
    """Exibe a página com os planos de assinatura disponíveis."""
    plans = Subscription.query.order_by(Subscription.price).all()
    return render_template('subscriptions.html', plans=plans)

@app.route('/subscribe/<int:plan_id>')
@login_required
def subscribe(plan_id):
    """Processa a assinatura de um usuário a um plano."""
    plan = Subscription.query.get_or_404(plan_id)

    # Lógica para calcular a data de término.
    # Nota: Usar 30 dias por mês é uma aproximação. Para maior precisão,
    # bibliotecas como `dateutil.relativedelta` podem ser usadas.
    end_date = datetime.now() + timedelta(days=30 * plan.duration_months)

    # Opcional: Lógica para lidar com assinaturas existentes (ex: estender, substituir).
    # Por enquanto, apenas cria uma nova.
    new_subscription = UserSubscription(
        user_id=current_user.id,
        subscription_id=plan.id,
        end_date=end_date
    )
    db.session.add(new_subscription)
    db.session.commit()

    flash(f"Você assinou o {plan.name} com sucesso! Seu acesso é válido até {end_date.strftime('%d/%m/%Y')}.", "success")
    return redirect(url_for('subscriptions_page'))

@app.route("/agenda", methods=["GET"])
@app.route("/agenda/<int:year>/<int:month>", methods=["GET"])
@login_required
def agenda(year=None, month=None):
    now = datetime.now()
   
    print(f"DEBUG: Argumentos recebidos na URL: {request.args}")
    selected_prof_id = request.args.get('professional_id', default=None, type=int)

    if year is None:
        year = now.year
    if month is None:
        month = now.month


    current_date = datetime(year, month, 1)

    prev_month_date = current_date - timedelta(days=1)
    previous_year = prev_month_date.year
    previous_month = prev_month_date.month

    _, num_days_in_month = calendar.monthrange(year, month)
    next_month_date = current_date + timedelta(days=num_days_in_month)
    next_year = next_month_date.year
    next_month = next_month_date.month

    calendar.setfirstweekday(calendar.SUNDAY)
    
    month_calendar = calendar.monthcalendar(year, month)

    portuguese_months = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    month_name = portuguese_months.get(month, "Mês Desconhecido")

    areas = Area.query.order_by(Area.name).all()

    return render_template(
        "agenda.html",
        year=year,
        month=month,
        previous_year=previous_year,
        previous_month=previous_month,
        next_year=next_year,
        next_month=next_month,
        month_name=month_name,
        calendar_data=month_calendar,
        areas=areas,
        selected_prof_id=selected_prof_id)

@app.route('/api/available_slots')
@login_required
def available_slots():
    """Retorna os horários disponíveis para um profissional em uma data específica."""
    professional_id = request.args.get('professional_id', type=int)
    date_str = request.args.get('date') # Formato esperado: YYYY-MM-DD

    if not professional_id or not date_str:
        return jsonify({'error': 'ID do profissional e data são obrigatórios'}), 400

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Formato de data inválido. Use YYYY-MM-DD.'}), 400

    # Define o horário de trabalho e a duração da consulta
    start_hour, end_hour, duration_minutes = 9, 18, 60

    # Busca agendamentos existentes para o dia
    start_of_day = datetime.combine(selected_date, time.min)
    end_of_day = datetime.combine(selected_date, time.max)

    existing_appointments = Appointment.query.filter(
        Appointment.professional_id == professional_id,
        Appointment.start_time.between(start_of_day, end_of_day)
    ).all()
    booked_slots = {appt.start_time.time() for appt in existing_appointments}

    # Gera todos os horários possíveis e filtra os já agendados
    available_slots = []
    current_time = time(start_hour, 0)
    while current_time < time(end_hour, 0):
        if current_time not in booked_slots:
            available_slots.append(current_time.strftime('%H:%M'))
        current_datetime = datetime.combine(datetime.today(), current_time) + timedelta(minutes=duration_minutes)
        current_time = current_datetime.time()

    return jsonify(available_slots)

@app.route('/api/book_appointment', methods=['POST'])
@login_required
def book_appointment():
    """Cria um novo agendamento, verificando a assinatura do usuário primeiro."""
    # PASSO MAIS IMPORTANTE: Verifica se o usuário tem uma assinatura ativa
    if not current_user.has_active_subscription:
        return jsonify({'error': 'É necessário ter uma assinatura ativa para marcar uma consulta.'}), 403 # 403 Forbidden

    data = request.get_json()
    professional_id = data.get('professional_id')
    date_str = data.get('date') # YYYY-MM-DD
    time_str = data.get('time') # HH:MM

    if not all([professional_id, date_str, time_str]):
        return jsonify({'error': 'Dados incompletos para o agendamento.'}), 400

    try:
        start_datetime = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
    except ValueError:
        return jsonify({'error': 'Formato de data ou hora inválido.'}), 400

    # Verifica se o horário ainda está vago (evita agendamentos duplicados)
    if Appointment.query.filter_by(professional_id=professional_id, start_time=start_datetime).first():
        return jsonify({'error': 'Este horário não está mais disponível. Por favor, escolha outro.'}), 409 # 409 Conflict

    professional = Professional.query.get_or_404(professional_id)
    new_appointment = Appointment(
        title=f"Consulta com {professional.full_name}",
        start_time=start_datetime,
        end_time=start_datetime + timedelta(hours=1),
        professional_id=professional_id,
        user_id=current_user.id
    )
    db.session.add(new_appointment)
    db.session.commit()

    return jsonify({'message': f'Consulta agendada com sucesso para {start_datetime.strftime("%d/%m/%Y às %H:%M")}.'}), 201

if __name__ == '__main__':
    app.run(debug=True)