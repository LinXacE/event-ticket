from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User
from database import db
from flask_bcrypt import Bcrypt
from datetime import datetime

bp = Blueprint('auth', __name__, url_prefix='/auth')

# IMPORTANT: This must be initialized in app.py with bcrypt.init_app(app)
bcrypt = Bcrypt()


# ================= LOGIN =================

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()

            next_page = request.args.get('next')
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard.home'))

        flash('Invalid username or password', 'danger')

    return render_template('auth/login.html')


# ================= REGISTER =================

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Full name safe build
        full_name = ((first_name or '') + ' ' + (last_name or '')).strip()

        # SECURITY: Do NOT allow users to choose role
        role = 'organizer'

        # Password match check
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('auth/register.html')

        # Username check
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return render_template('auth/register.html')

        # Email check
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('auth/register.html')

        # Hash password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        new_user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hashed_password,
            role=role
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


# ================= LOGOUT =================

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))
