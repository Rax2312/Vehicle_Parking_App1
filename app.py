from flask import Flask, redirect, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
from models.models import db, User

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = 'supersecretkey'  
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(app.instance_path, exist_ok=True)

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register blueprints
from controllers.auth import auth_bp
from controllers.admin import admin_bp
from controllers.user import user_bp
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)

@app.before_request
def create_tables_and_admin():
    if not hasattr(app, 'db_initialized'):
        db.create_all()
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@gmail.com',
                role='admin',
                first_name='Admin',
                last_name='User',
                flagged=False
            )
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
        app.db_initialized = True

@app.route('/')
def home():
    return render_template('landing.html')

if __name__ == '__main__':
    print("🚗 Vehicle Parking App Starting...")
    print("📍 Server running at: http://127.0.0.1:5173")
    print("👤 Admin credentials: admin / admin")
    print("=" * 50)
    app.run(debug=False, host='127.0.0.1', port=5173) 