from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, send_file
)

from flask_sqlalchemy import SQLAlchemy

from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)

from werkzeug.security import generate_password_hash, check_password_hash

from services.generator import generate_questions
from services.evaluator import evaluate_answer
from services.pdf_report import generate_pdf_report

import os


app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

db_path = os.path.join(BASE_DIR, "instance", "interview.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)

app.config["SECRET_KEY"] = "change_this_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


class Interview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(50), nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp()
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )


class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    score = db.Column(db.Integer)
    feedback = db.Column(db.Text)

    interview_id = db.Column(
        db.Integer,
        db.ForeignKey("interview.id"),
        nullable=False
    )


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("Email already exists.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        new_user = User(
            name=name,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful. Please login.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():

    interviews = Interview.query.filter_by(
        user_id=current_user.id
    ).all()

    interview_ids = [interview.id for interview in interviews]

    results = Result.query.filter(
        Result.interview_id.in_(interview_ids)
    ).all() if interview_ids else []

    total_interviews = len(interviews)
    total_questions = len(results)

    if results:
        scores = [result.score for result in results]

        average_score = round(sum(scores) / len(scores), 2)
        highest_score = max(scores)
        lowest_score = min(scores)

    else:
        average_score = 0
        highest_score = 0
        lowest_score = 0

    score_labels = []
    score_values = []

    recent_interviews = interviews[-10:]

    for index, interview in enumerate(recent_interviews, start=1):

        interview_results = Result.query.filter_by(
            interview_id=interview.id
        ).all()

        if interview_results:
            interview_scores = [r.score for r in interview_results]

            interview_average = round(
                sum(interview_scores) / len(interview_scores),
                2
            )

            score_labels.append(f"Interview {index}")
            score_values.append(interview_average)

    return render_template(
        "dashboard.html",
        user=current_user,
        total_interviews=total_interviews,
        total_questions=total_questions,
        average_score=average_score,
        highest_score=highest_score,
        lowest_score=lowest_score,
        score_labels=score_labels,
        score_values=score_values
    )


@app.route("/start-interview", methods=["POST"])
@login_required
def start_interview():

    role = request.form["role"]
    difficulty = request.form["difficulty"]

    interview = Interview(
        role=role,
        difficulty=difficulty,
        user_id=current_user.id
    )

    db.session.add(interview)
    db.session.commit()

    questions = generate_questions(role)

    timer_minutes = 40

    return render_template(
        "interview.html",
        questions=questions,
        interview_id=interview.id,
        difficulty=difficulty,
        timer_minutes=timer_minutes
    )


@app.route("/submit-interview", methods=["POST"])
@login_required
def submit_interview():

    interview_id = request.form["interview_id"]

    total_questions = int(
        request.form["total_questions"]
    )

    results = []
    total_score = 0

    for i in range(1, total_questions + 1):

        question = request.form[f"question_{i}"]
        answer = request.form[f"answer_{i}"]

        keywords = request.form[
            f"keywords_{i}"
        ].split(",")

        evaluation = evaluate_answer(
            answer,
            keywords
        )

        result = Result(
            question=question,
            answer=answer,
            score=evaluation["score"],
            feedback=evaluation["feedback"],
            interview_id=interview_id
        )

        db.session.add(result)

        results.append({
            "question": question,
            "answer": answer,
            "score": evaluation["score"],
            "feedback": evaluation["feedback"],
            "keywords": keywords
        })

        total_score += evaluation["score"]

    db.session.commit()

    average_score = round(
        total_score / total_questions,
        2
    )

    weak_areas = []

    for result in results:
        if result["score"] < 50:
            weak_areas.append(result["question"])

    clean_weak_areas = []

    for q in weak_areas:
        q = q.replace("Explain ", "")
        q = q.replace("What is the difference between ", "")
        q = q.replace("What are ", "")
        q = q.replace("What is ", "")
        q = q.replace("?", "")

        clean_weak_areas.append(q.strip())

    weak_areas = list(set(clean_weak_areas))

    roadmap = []

    for index, area in enumerate(weak_areas, start=1):
        roadmap.append({
            "day": f"Day {index}",
            "topic": area,
            "task": (
                f"Revise {area}, study examples, "
                "and practice related interview questions."
            )
        })

    if weak_areas:
        roadmap.append({
            "day": f"Day {len(weak_areas) + 1}",
            "topic": "Mock Interview",
            "task": "Retake a mock interview and focus on improving weak areas."
        })

    return render_template(
        "result.html",
        results=results,
        average_score=average_score,
        interview_id=interview_id,
        weak_areas=weak_areas,
        roadmap=roadmap
    )


@app.route("/download-report/<int:interview_id>")
@login_required
def download_report(interview_id):

    results_data = Result.query.filter_by(
        interview_id=interview_id
    ).all()

    results = []
    total_score = 0

    for r in results_data:
        results.append({
            "question": r.question,
            "answer": r.answer,
            "score": r.score,
            "feedback": r.feedback
        })

        total_score += r.score

    if results_data:
        average_score = round(
            total_score / len(results_data),
            2
        )
    else:
        average_score = 0

    file_path = f"report_{interview_id}.pdf"

    generate_pdf_report(
        file_path,
        results,
        average_score
    )

    return send_file(
        file_path,
        as_attachment=True
    )


@app.route("/history")
@login_required
def history():

    interviews = Interview.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Interview.created_at.desc()
    ).all()

    return render_template(
        "history.html",
        interviews=interviews
    )
@app.route("/notes")
@login_required
def notes():

    notes_data = {
        "SDE": [
            {
                "title": "Object-Oriented Programming",
                "definition": "OOP is a programming approach that organizes code using classes and objects.",
                "points": [
                    "Class is a blueprint for objects.",
                    "Object is an instance of a class.",
                    "Encapsulation binds data and methods together.",
                    "Inheritance allows code reuse.",
                    "Polymorphism allows one interface to have many forms.",
                    "Abstraction hides implementation details."
                ],
                "questions": [
                    "What is OOP?",
                    "Explain the four pillars of OOP.",
                    "Difference between abstraction and encapsulation?",
                    "What is inheritance?",
                    "What is polymorphism?"
                ]
            },
            {
                "title": "SQL Joins",
                "definition": "SQL joins are used to combine rows from two or more tables based on a related column.",
                "points": [
                    "INNER JOIN returns matching records from both tables.",
                    "LEFT JOIN returns all records from the left table.",
                    "RIGHT JOIN returns all records from the right table.",
                    "FULL JOIN returns all records from both tables.",
                    "Joins are commonly used in relational databases."
                ],
                "questions": [
                    "Explain SQL joins.",
                    "Difference between INNER JOIN and LEFT JOIN?",
                    "What is SELF JOIN?",
                    "What is CROSS JOIN?",
                    "Difference between JOIN and UNION?"
                ]
            },
            {
                "title": "Git and Version Control",
                "definition": "Git is a distributed version control system used to track code changes and collaborate with developers.",
                "points": [
                    "Repository stores project files and history.",
                    "Commit saves a snapshot of changes.",
                    "Branch allows parallel development.",
                    "Merge combines changes from branches.",
                    "GitHub is a cloud platform for hosting Git repositories."
                ],
                "questions": [
                    "What is Git?",
                    "What is a commit?",
                    "Difference between Git and GitHub?",
                    "What is branching?",
                    "What is merge conflict?"
                ]
            }
        ],

        "Data Analyst": [
            {
                "title": "SQL Basics",
                "definition": "SQL is used to store, retrieve, and manipulate data in relational databases.",
                "points": [
                    "SELECT retrieves data.",
                    "WHERE filters records.",
                    "GROUP BY groups rows.",
                    "ORDER BY sorts results.",
                    "HAVING filters grouped data."
                ],
                "questions": [
                    "What is SQL?",
                    "Difference between WHERE and HAVING?",
                    "What is GROUP BY?",
                    "What is ORDER BY?",
                    "What is a primary key?"
                ]
            },
            {
                "title": "Statistics",
                "definition": "Statistics helps analyze and interpret data using mathematical methods.",
                "points": [
                    "Mean is the average value.",
                    "Median is the middle value.",
                    "Mode is the most frequent value.",
                    "Variance measures spread.",
                    "Standard deviation shows data dispersion."
                ],
                "questions": [
                    "What is mean, median, and mode?",
                    "What is standard deviation?",
                    "What is variance?",
                    "What is correlation?",
                    "Difference between correlation and causation?"
                ]
            },
            {
                "title": "Data Visualization",
                "definition": "Data visualization represents data using charts, graphs, and dashboards.",
                "points": [
                    "Bar charts compare categories.",
                    "Line charts show trends.",
                    "Pie charts show proportions.",
                    "Scatter plots show relationships.",
                    "Dashboards summarize key insights."
                ],
                "questions": [
                    "Why is data visualization important?",
                    "When do you use a bar chart?",
                    "When do you use a line chart?",
                    "What is a dashboard?",
                    "What makes a good visualization?"
                ]
            }
        ],

        "ML Engineer": [
            {
                "title": "Machine Learning Basics",
                "definition": "Machine learning enables systems to learn patterns from data and make predictions.",
                "points": [
                    "Supervised learning uses labeled data.",
                    "Unsupervised learning finds hidden patterns.",
                    "Regression predicts continuous values.",
                    "Classification predicts categories.",
                    "Training data is used to teach the model."
                ],
                "questions": [
                    "What is machine learning?",
                    "Difference between supervised and unsupervised learning?",
                    "What is regression?",
                    "What is classification?",
                    "What is training data?"
                ]
            },
            {
                "title": "Model Evaluation",
                "definition": "Model evaluation measures how well a machine learning model performs.",
                "points": [
                    "Accuracy measures correct predictions.",
                    "Precision measures correct positive predictions.",
                    "Recall measures how many positives were found.",
                    "F1-score balances precision and recall.",
                    "Confusion matrix shows prediction results."
                ],
                "questions": [
                    "What is accuracy?",
                    "What is precision?",
                    "What is recall?",
                    "What is F1-score?",
                    "What is confusion matrix?"
                ]
            },
            {
                "title": "Overfitting and Underfitting",
                "definition": "Overfitting happens when a model memorizes training data, while underfitting happens when it fails to learn patterns.",
                "points": [
                    "Overfitting gives high training accuracy but low test accuracy.",
                    "Underfitting gives poor performance on both train and test data.",
                    "Regularization helps reduce overfitting.",
                    "Cross-validation helps test model generalization.",
                    "More data can reduce overfitting."
                ],
                "questions": [
                    "What is overfitting?",
                    "What is underfitting?",
                    "How to reduce overfitting?",
                    "What is regularization?",
                    "What is cross-validation?"
                ]
            }
        ]
    }

    return render_template(
        "notes.html",
        notes_data=notes_data
    )
@app.route("/logout")
@login_required
def logout():

    logout_user()
    flash("Logged out successfully.")

    return redirect(url_for("login"))


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)