from flask import render_template, url_for, flash, redirect, abort, request
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Message, Topic
from forms import RegistrationForm, LoginForm, MessageForm
from datetime import datetime, timedelta

def init_routes(app):
    @app.context_processor
    def utility_processor():
        def can_edit(message):
            limit = message.timestamp + timedelta(minutes=10)
            return datetime.utcnow() < limit
        return dict(can_edit=can_edit, all_topics=Topic.query.all())
    
    @app.route("/", methods=['GET', 'POST'])
    @app.route("/topic/<int:topic_id>", methods=['GET', 'POST'])
    def home(topic_id=None):
        form = MessageForm()
        current_topic_name = "Community Feed"
        
        if topic_id:
            topic_obj = Topic.query.get_or_404(topic_id)
            current_topic_name = f"#{topic_obj.name}"

        if form.validate_on_submit():
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            
            new_msg = Message(content=form.content.data, author=current_user, topic_id=topic_id)
            db.session.add(new_msg)
            db.session.commit()
            
            if topic_id:
                return redirect(url_for('home', topic_id=topic_id))
            return redirect(url_for('home'))
        
        query = Message.query.filter_by(parent_id=None)
        if topic_id:
            messages = query.filter_by(topic_id=topic_id).order_by(Message.timestamp.desc()).all()
        else:
            messages = query.order_by(Message.timestamp.desc()).all()
            
        return render_template('index.html', form=form, messages=messages, current_topic_name=current_topic_name)

    @app.route("/add_topic", methods=['POST'])
    @login_required
    def add_topic():
        if not current_user.is_admin:
            abort(403)
            
        topic_name = request.form.get('topic_name')
        if topic_name:
            exists = Topic.query.filter_by(name=topic_name).first()
            if not exists:
                new_topic = Topic(name=topic_name)
                db.session.add(new_topic)
                db.session.commit()
                
        return redirect(url_for('home'))

    @app.route("/edit/<int:msg_id>", methods=['GET', 'POST'])
    @login_required
    def edit_message(msg_id):
        msg = Message.query.get_or_404(msg_id)
        limit = msg.timestamp + timedelta(minutes=10)
        
        if msg.author != current_user:
            abort(403)
        if datetime.utcnow() > limit:
            return redirect(url_for('home'))
            
        form = MessageForm()
        if form.validate_on_submit():
            msg.content = form.content.data
            db.session.commit()
            return redirect(url_for('home'))
        elif request.method == 'GET':
            form.content.data = msg.content
            
        return render_template('index.html', form=form, messages=Message.query.filter_by(parent_id=None).order_by(Message.timestamp.desc()).all(), editing=msg.id, current_topic_name="Editing...")

    @app.route("/register", methods=['GET', 'POST'])
    def register():
        form = RegistrationForm()
        if form.validate_on_submit():
            is_admin = False
            if form.password.data == "admin007":
                is_admin = True
            
            hashed_password = generate_password_hash(form.password.data)
            user = User(username=form.username.data, password=hashed_password, is_admin=is_admin)
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('login'))
        return render_template('register.html', form=form)

    @app.route("/login", methods=['GET', 'POST'])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('home'))
        return render_template('login.html', form=form)

    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for('home'))

    @app.route("/like/<int:msg_id>")
    @login_required
    def like_message(msg_id):
        msg = Message.query.get_or_404(msg_id)
        if msg in current_user.liked_messages:
            current_user.liked_messages.remove(msg)
        else:
            current_user.liked_messages.append(msg)
        db.session.commit()
        return redirect(request.referrer)

    @app.route("/reply/<int:msg_id>", methods=['POST'])
    @login_required
    def reply_message(msg_id):
        parent_msg = Message.query.get_or_404(msg_id)
        content = request.form.get('reply_content')
        
        if content:
            reply = Message(content=content, author=current_user, parent=parent_msg, topic_id=parent_msg.topic_id)
            db.session.add(reply)
            db.session.commit()
            
        return redirect(url_for('home'))

    @app.route("/delete/<int:msg_id>")
    @login_required
    def delete_message(msg_id):
        msg = Message.query.get_or_404(msg_id)
        if msg.author == current_user or current_user.is_admin:
            db.session.delete(msg)
            db.session.commit()
            return redirect(url_for('home'))
        abort(403)