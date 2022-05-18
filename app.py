from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json
from bson import ObjectId
from flask import Flask, abort, jsonify, request, Response
from flask_cors import CORS
import jwt
from pymongo import MongoClient
# from bson.json_util import loads, dumps


SECRET_KEY = 'turtle'


app = Flask(__name__)
cors = CORS(app, resources={
            r'*': {'origins': ['http://127.0.0.1:5000', 'http://127.0.0.1:5500']}})
client = MongoClient('localhost', 27017)
db = client.turtlegram


def authorize(f):
    @wraps(f)
    def decorated_function():
        if not 'Authorization' in request.headers:
            abort(401)
        token = request.headers['Authorization']
        try:
            user = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        except:
            abort(401)
        return f(user)
    return decorated_function


@app.route("/")
@authorize
def hello_world(user):
    return jsonify({'message': 'success'})


@app.route("/signup", methods=['POST'])
def sign_up():
    data = json.loads(request.data)

    # 이메일 중복시 에러처리

    # 비밀번호 해싱
    pw = data.get('password', None)
    hashed_password = hashlib.sha256(pw.encode('utf-8')).hexdigest()

    doc = {
        'email': data.get('email'),
        'password': hashed_password
    }

    db.users.insert_one(doc)

    return jsonify({'message': 'success'})


@app.route("/login", methods=["POST"])
def login():
    data = json.loads(request.data)

    email = data.get("email")
    password = data.get("password")
    hashed_pw = hashlib.sha256(password.encode('utf-8')).hexdigest()

    result = db.users.find_one({
        'email': email,
        'password': hashed_pw
    })

    if result is None:
        return jsonify({"message": "아이디나 비밀번호가 옳지 않습니다."}), 401

    payload = {
        'id': str(result["_id"]),
        'exp': datetime.utcnow() + timedelta(seconds=60 * 60 * 24)  # 로그인 24시간 유지
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

    return jsonify({"message": "success", "token": token})


@app.route("/getuserinfo", methods=["GET"])
@authorize
def get_user_info(user):
    result = db.users.find_one({
        '_id': ObjectId(user["id"])
    })

    return jsonify({"message": "success", "email": result["email"]})


@app.route("/article", methods=["POST"])
@authorize
def post_article(user):
    data = json.loads(request.data)

    db_user = db.users.find_one({'_id': ObjectId(user.get('id'))})

    now = datetime.now().strftime("%H:%M:%S")
    doc = {
        'title': data.get('title', None),
        'content': data.get('content', None),
        'user': user['id'],
        'user_email': db_user['email'],
        'time': now,
    }

    db.article.insert_one(doc)

    return jsonify({"message": "success"})


@app.route("/article", methods=["GET"])
def get_article():
    articles = list(db.article.find())
    for article in articles:
        article["_id"] = str(article["_id"])
    return jsonify({"message": "success", "articles": articles})


if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)
