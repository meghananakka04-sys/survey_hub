from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

app = Flask(__name__)

# Basic config
app.config['SECRET_KEY'] = 'dev-secret-key-change-later'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///survey_hub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ------------- MODELS -------------

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    college = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    surveys = db.relationship('Survey', backref='creator', lazy=True)
    phone = db.Column(db.String(20), nullable=True)
    is_alumni = db.Column(db.Boolean, default=False)
    batch_year = db.Column(db.String(20), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    organisation = db.Column(db.String(150), nullable=True)
    designation = db.Column(db.String(150), nullable=True)


class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    external_link = db.Column(db.String(300), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    domain_tags = db.Column(db.String(200), nullable=True)
    target_audience = db.Column(db.String(200), nullable=True)
    time_estimate = db.Column(db.String(20), nullable=True)
    college = db.Column(db.String(120), nullable=True)
    context_info = db.Column(db.String(200), nullable=True)
    deadline = db.Column(db.Date, nullable=True)
    space = db.Column(db.String(50), nullable=True)
    is_open = db.Column(db.Boolean, default=True)
    click_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ------------- ROUTES -------------

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('Email already registered', 'danger')
            return redirect(url_for('signup'))

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(name=name, email=email, password_hash=pw_hash)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('browse'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('browse'))
        else:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/profile')
@login_required
def profile():
    # View-only profile page; editing happens on /profile/edit
    return render_template('profile.html')


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.name = request.form['name']
        current_user.email = request.form['email']
        current_user.phone = request.form.get('phone') or None
        current_user.college = request.form.get('college') or None
        current_user.role = request.form.get('role') or None

        is_alumni_value = request.form.get('is_alumni')
        current_user.is_alumni = True if is_alumni_value == 'on' else False
        current_user.batch_year = request.form.get('batch_year') or None
        current_user.organisation = request.form.get('organisation') or None
        current_user.designation = request.form.get('designation') or None
        current_user.summary = request.form.get('summary') or None

        db.session.commit()
        flash('Profile updated', 'success')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html')


@app.route('/browse')
def browse():
    space_filter = request.args.get('space')
    type_filter = request.args.get('type')
    domain_filter = request.args.get('domain')
    college_filter = request.args.get('college')
    time_filter = request.args.get('time')
    sort = request.args.get('sort', 'newest')
    open_only = request.args.get('open_only')
    query = Survey.query
    if space_filter:
        query = query.filter(Survey.space == space_filter)
    if type_filter:
        query = query.filter(Survey.type == type_filter)
    if domain_filter:
        query = query.filter(Survey.domain_tags.ilike(f"%{domain_filter}%"))
    if college_filter:
        query = query.filter(Survey.college.ilike(f"%{college_filter}%"))
    if time_filter:
        query = query.filter(Survey.time_estimate == time_filter)
    if open_only == '1':
        query = query.filter(Survey.is_open == True)
    if sort == 'closing':
        query = query.order_by(Survey.deadline.asc().nulls_last())
    else:
        query = query.order_by(Survey.created_at.desc())
    surveys = query.all()
    # Group surveys by space (category)
    categories = {}
    for s in surveys:
        space_key = s.space or 'general'
        categories.setdefault(space_key, []).append(s)
    # Define display names for spaces
    space_labels = {
        'case_comps': 'Case comps',
        'college_surveys': 'College surveys',
        'general_research': 'General research',
        'self_projects': 'Self projects',
        'general': 'General'
    }
    return render_template(
        'browse.html',
        surveys=surveys,
        categories=categories,
        space_labels=space_labels,
        space_filter=space_filter,
        type_filter=type_filter,
        domain_filter=domain_filter,
        college_filter=college_filter,
        time_filter=time_filter,
        sort=sort,
        open_only=open_only,
    )


@app.route('/survey/<int:survey_id>')
def survey_detail(survey_id):
    survey = Survey.query.get_or_404(survey_id)
    return render_template('survey_detail.html', survey=survey)


@app.route('/survey/<int:survey_id>/open')
def open_survey(survey_id):
    survey = Survey.query.get_or_404(survey_id)
    survey.click_count = (survey.click_count or 0) + 1
    db.session.commit()
    return redirect(survey.external_link)


@app.route('/create-survey', methods=['GET', 'POST'])
@login_required
def create_survey():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        external_link = request.form['external_link']
        type_ = request.form['type']
        space = request.form['space']
        domain_tags = request.form['domain_tags']
        target_audience = request.form['target_audience']
        time_estimate = request.form['time_estimate']
        college = request.form.get('college') or current_user.college
        context_info = request.form['context_info']
        deadline_str = request.form['deadline']
        deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None

        survey = Survey(
            user_id=current_user.id,
            title=title,
            description=description,
            external_link=external_link,
            type=type_,
            space=space,
            domain_tags=domain_tags,
            target_audience=target_audience,
            time_estimate=time_estimate,
            college=college,
            context_info=context_info,
            deadline=deadline,
            is_open=True
        )
        db.session.add(survey)
        db.session.commit()
        return redirect(url_for('survey_detail', survey_id=survey.id))

    return render_template('create_survey.html')


@app.route('/survey/<int:survey_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_survey(survey_id):
    survey = Survey.query.get_or_404(survey_id)
    if survey.creator != current_user:
        abort(403)

    if request.method == 'POST':
        survey.title = request.form['title']
        survey.description = request.form['description']
        survey.external_link = request.form['external_link']
        survey.type = request.form['type']
        survey.space = request.form['space']
        survey.domain_tags = request.form.get('domain_tags') or None
        survey.target_audience = request.form.get('target_audience') or None
        survey.time_estimate = request.form.get('time_estimate') or None
        survey.college = request.form.get('college') or None
        survey.context_info = request.form.get('context_info') or None
        deadline_str = request.form.get('deadline')
        survey.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None

        db.session.commit()
        flash('Survey updated successfully', 'success')
        return redirect(url_for('survey_detail', survey_id=survey.id))

    return render_template('edit_survey.html', survey=survey)


@app.route('/my-surveys')
@login_required
def my_surveys():
    surveys = Survey.query.filter_by(user_id=current_user.id).order_by(Survey.created_at.desc()).all()
    return render_template('my_surveys.html', surveys=surveys)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
