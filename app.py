from flask import Flask, render_template, request, redirect, url_for, session
from flask_babel import Babel, gettext
from config import Config
from flask_sqlalchemy import SQLAlchemy
import random
import datetime
import nltk
import wikipediaapi
from geopy.geocoders import Nominatim
import requests

app = Flask(__name__)
app.config.from_object(Config)
babel = Babel(app)
db = SQLAlchemy(app)

# Инициализация NLTK
nltk.download('wordnet')
nltk.download('omw-1.4')  # Загрузка Open Multilingual Wordnet
from nltk.corpus import wordnet

# Инициализация Wikipedia API с указанием user_agent
wiki_wiki = wikipediaapi.Wikipedia(
    language='de',
    user_agent='EducationalTrainer/1.0 (https://example.com; contact@example.com)'
)

# Инициализация Geopy
geolocator = Nominatim(user_agent="educational_trainer")

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    trainer = db.Column(db.String(64), nullable=False)
    correct = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.datetime.utcnow)
    points = db.Column(db.Integer, nullable=False)

def get_locale():
    return request.accept_languages.best_match(['en', 'de'])

@app.before_request
def before_request():
    session.permanent = True
    app.permanent_session_lifetime = datetime.timedelta(days=5)

@app.context_processor
def inject_locale():
    return dict(get_locale=lambda: get_locale())

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/parent')
def parent():
    results = Result.query.all()
    total_correct = sum(1 for result in results if result.correct)
    total_incorrect = len(results) - total_correct
    total_points = sum(result.points for result in results)
    total_euro = total_points * session.get('price_per_point', 1) / 100
    return render_template('parent.html', results=results, total_correct=total_correct, total_incorrect=total_incorrect, total_points=total_points, total_euro=total_euro)

@app.route('/child')
def child():
    return render_template('child.html')

@app.route('/contract', methods=['GET', 'POST'])
def contract():
    if request.method == 'POST':
        # Сохранение контракта
        session['difficulty'] = int(request.form['difficulty'])
        session['correct_points'] = int(request.form['correct_points'])
        session['incorrect_points'] = int(request.form['incorrect_points'])
        session['price_per_point'] = int(request.form['price_per_point'])
        return redirect(url_for('home'))
    return render_template('contract.html')

def generate_math_question():
    num1 = random.randint(10, 99)
    num2 = random.randint(10, 99)
    operation = random.choice(['+', '-', '*', '/'])
    
    if operation == '+':
        correct_answer = num1 + num2
    elif operation == '-':
        correct_answer = num1 - num2
    elif operation == '*':
        correct_answer = num1 * num2
    elif operation == '/':
        correct_answer = round(num1 / num2, 2)
    
    question = f"Was ist {num1} {operation} {num2}?"
    return question, correct_answer

def generate_synonym_question(language='en'):
    if language == 'de':
        words = list(wordnet.words())
        word = random.choice(words)
        response = requests.get(f"https://www.openthesaurus.de/synonyme/search?q={word}&format=application/json")
        data = response.json()
        synonyms = []
        for synset in data.get('synsets', []):
            for term in synset.get('terms', []):
                synonyms.append(term['term'])
        if synonyms:
            synonym = random.choice(synonyms)
        else:
            synonym = word
        question = f"Was ist ein Synonym für {word}?"
    else:
        words = list(wordnet.words())
        word = random.choice(words)
        synonyms = wordnet.synsets(word)
        if synonyms:
            synonym = random.choice(synonyms).lemmas()[0].name()
        else:
            synonym = word
        question = f"What is a synonym for {word}?"
    return question, synonym

def generate_history_question():
    page = wiki_wiki.page(random.choice(["Napoleon", "Römisches_Reich", "Zweiter_Weltkrieg"]))
    date = page.summary.split()[:10]
    question = f"Was ist das Ereignis zu dem Datum: {' '.join(date)}?"
    return question, page.title

def generate_geography_question():
    location = geolocator.geocode("Berlin")
    question = "Was ist die Hauptstadt von Deutschland?"
    return question, location.address

def generate_biology_question():
    question = "Zu welcher Klasse gehört Homo sapiens?"
    answer = "Säugetiere"
    return question, answer

def generate_literature_question():
    question = "Wer ist der Autor von 'Faust'?"
    answer = "Johann Wolfgang von Goethe"
    return question, answer

@app.route('/trainer/<trainer_type>')
def trainer(trainer_type):
    if trainer_type == "math":
        question, correct_answer = generate_math_question()
    elif trainer_type == "english":
        question, correct_answer = generate_synonym_question(language='en')
    elif trainer_type == "german":
        question, correct_answer = generate_synonym_question(language='de')
    elif trainer_type == "history":
        question, correct_answer = generate_history_question()
    elif trainer_type == "geography":
        question, correct_answer = generate_geography_question()
    elif trainer_type == "biology":
        question, correct_answer = generate_biology_question()
    elif trainer_type == "literature":
        question, correct_answer = generate_literature_question()
    else:
        question, correct_answer = "Unbekannter Trainer", ""
    
    answers = [correct_answer]
    while len(answers) < 4:
        if isinstance(correct_answer, str):
            # Генерация случайных строк для неправильных ответов
            wrong_answer = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(len(correct_answer)))
        else:
            # Генерация случайных чисел для неправильных ответов
            wrong_answer = correct_answer + random.randint(-10, 10)
        if wrong_answer not in answers:
            answers.append(wrong_answer)
    random.shuffle(answers)
    return render_template('trainer.html', question=question, answers=answers, correct_answer=correct_answer, time=session.get('difficulty', 10), trainer_type=trainer_type)

@app.route('/check_answer', methods=['POST'])
def check_answer():
    user_answer = request.form['answer']
    correct_answer = request.form['correct_answer']
    correct = user_answer == correct_answer
    points = session.get('correct_points', 10) if correct else -session.get('incorrect_points', 5)
    result = Result(user_id=session.get('user_id', 1), trainer=request.form['trainer_type'], correct=correct, points=points)
    db.session.add(result)
    db.session.commit()
    return redirect(url_for('trainer', trainer_type=request.form['trainer_type']))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
    