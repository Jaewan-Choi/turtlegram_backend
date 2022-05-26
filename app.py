from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json
from xmlrpc.client import ResponseError
from bson import ObjectId
from flask import Flask, abort, jsonify, request, Response
from flask_cors import CORS
import jwt
from pymongo import MongoClient
from bson.json_util import loads, dumps

SECRET_KEY = 'turtle'

app = Flask(__name__)
cors = CORS(app, resources={r"*": {"origins": "*"}})
client = MongoClient('localhost', 27017)
db = client.turtlegram


def authorize(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not 'Authorization' in request.headers:
            abort(401)
        token = request.headers['Authorization']
        try:
            user = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        except:
            abort(401)
        return f(user, *args, **kwargs)
    return decorated_function


@app.route("/")
@authorize
def hello_world(user):
    print(user)
    return jsonify({'message': 'success'})


@app.route("/signup", methods=["POST"])
def sign_up():
    data = json.loads(request.data)
    # data = loads(request.data)
    print(data.get('email'))
    print(data["password"])

    # 이메일 중복시 에러처리

    # 비밀번호 해싱
    pw = data.get('password', None)
    hashed_password = hashlib.sha256(pw.encode('utf-8')).hexdigest()

    doc = {
        'email': data.get('email'),
        'password': hashed_password
    }

    # doc = {
    #     'email': data.get('email'),
    #     'password': data.get('password')
    # }

    print(doc)
    user = db.users.insert_one(doc)
    print(doc)

    return jsonify({"status": "success"})

    # # dump 사용
    # json_doc = dumps(doc)
    # print(json_doc)
    # return json_doc


@app.route("/login", methods=["POST"])
def login():
    data = json.loads(request.data)

    email = data.get("email")
    password = data.get("password")
    hashed_pw = hashlib.sha256(password.encode('utf-8')).hexdigest()
    print(hashed_pw)

    result = db.users.find_one({
        'email': email,
        'password': hashed_pw
    })
    print(result)

    if result is None:
        return jsonify({"message": "아이디나 비밀번호가 옳지 않습니다."}), 401

    payload = {
        'id': str(result["_id"]),
        'exp': datetime.utcnow() + timedelta(seconds=60 * 60 * 24)  # 로그인 24시간 유지
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    print(token)

    return jsonify({"message": "success", "token": token})


@app.route("/getuserinfo", methods=["GET"])
@authorize
def get_user_info(user):
    result = db.users.find_one({
        '_id': ObjectId(user["id"])
    })

    return jsonify({"message": "success", "email": result["email"], "id": user["id"]})


@app.route("/article", methods=["POST"])
@authorize
def post_article(user):
    data = json.loads(request.data)
    print(data)

    db_user = db.users.find_one({'_id': ObjectId(user.get('id'))})

    now = datetime.now().strftime("%H:%M:%S")
    doc = {
        'title': data.get('title', None),
        'content': data.get('content', None),
        'user': user['id'],
        'user_email': db_user['email'],
        'time': now,
    }
    print(doc)

    db.article.insert_one(doc)

    return jsonify({"message": "success"})


@app.route("/article", methods=["GET"])
def get_article():
    articles = list(db.article.find())
    for article in articles:
        article["_id"] = str(article["_id"])
    return jsonify({"message": "success", "articles": articles})


@app.route("/article/<article_id>", methods=["GET"])
def get_article_detail(article_id):
    article = db.article.find_one({"_id": ObjectId(article_id)})
    comments = list(db.comment.find({"article": article_id}))
    likes = list(db.like.find({"article": article_id}))
    if article:
        article["_id"] = str(article["_id"])
        article["comments"] = json.loads(dumps(comments))
        article["likes_count"] = len(likes)
        return jsonify({"message": "success", "article": article})
    else:
        return jsonify({"message": "fail"}), 404


@app.route("/article/<article_id>", methods=["PATCH"])
@authorize
def patch_article_detail(user, article_id):

    data = json.loads(request.data)
    title = data.get("title")
    content = data.get("content")

    article = db.article.update_one({"_id": ObjectId(article_id), "user": user["id"]}, {
        "$set": {"title": title, "content": content}})

    if article.matched_count:
        return jsonify({"message": "success"})
    else:
        return jsonify({"message": "fail"}), 403


@app.route("/article/<article_id>", methods=["DELETE"])
@authorize
def delete_article_detail(user, article_id):

    article = db.article.delete_one(
        {"_id": ObjectId(article_id), "user": user["id"]})

    if article.deleted_count:
        return jsonify({"message": "success"})
    else:
        return jsonify({"message": "fail"}), 403


@app.route("/article/<article_id>/comment", methods=["POST"])
@authorize
def post_comment(user, article_id):
    data = json.loads(request.data)
    print(data)

    db_user = db.users.find_one({'_id': ObjectId(user.get('id'))})

    now = datetime.now().strftime("%H:%M:%S")
    doc = {
        'article': article_id,
        'content': data.get('content', None),
        'user': user['id'],
        'user_email': db_user['email'],
        'time': now,
    }
    print(doc)

    db.comment.insert_one(doc)

    return jsonify({"message": "success"})


@app.route("/article/<article_id>/comment", methods=["GET"])
def get_comment(article_id):
    comments = list(db.comment.find({"article": article_id}))
    json_comments = json.loads(dumps(comments))
    return jsonify({"message": "success", "comments": json_comments})


@app.route("/article/<article_id>/like", methods=["POST"])
@authorize
def post_like(user, article_id):
    print(user, article_id)
    db_user = db.users.find_one({'_id': ObjectId(user.get('id'))})

    now = datetime.now().strftime("%H:%M:%S")
    doc = {
        'article': article_id,
        'user': user['id'],
        'user_email': db_user['email'],
        'time': now,
    }
    print(doc)

    db.like.insert_one(doc)

    return jsonify({"message": "success"})


@app.route("/article/<article_id>/like", methods=["DELETE"])
@authorize
def delete_like(user, article_id):
    print(user, article_id)

    result = db.like.delete_one({"article": article_id, "user": user["id"]})
    if result.deleted_count:
        return jsonify({"message": "success"})
    else:
        return jsonify({"message": "fail"}), 400


@app.route("/article/<article_id>/like", methods=["GET"])
@authorize
def get_like(user, article_id):
    print(user, article_id)

    result = db.like.find_one({"article": article_id, "user": user["id"]})
    if result:
        return jsonify({"message": "success", "liked": True})
    else:
        return jsonify({"message": "fail", "liked": False})


if __name__ == '__main__':
    app.run('0.0.0.0', port=5002, debug=True)
