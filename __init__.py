from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from threading import Timer
import plotly
import plotly.graph_objs as go
import json
import time
import base64
import smtplib

app = Flask(__name__)
app.config['SECRET_KEY'] = '7894645'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///polling.db'
db = SQLAlchemy(app)

#Database Models
class Users(db.Model):
	id = db.Column(db.Integer, primary_key = True)
	name = db.Column(db.String(100))
	uname = db.Column(db.String(50))
	aadhar = db.Column(db.String(25))
	email = db.Column(db.String(55))
	unique = db.Column(db.Integer, db.ForeignKey('vote.id'),default=0)

class Check(db.Model):
	id = db.Column(db.Integer, primary_key = True)
	username = db.Column(db.String, db.ForeignKey('users.uname'))
	v_id = db.Column(db.Integer, db.ForeignKey('vote.id'))

class Vote(db.Model):
	id = db.Column(db.Integer, primary_key = True)
	title = db.Column(db.String(150))
	duration = db.Column(db.Integer)
	option = db.relationship('Option', backref='opt', lazy=True)

class Option(db.Model):
	id = db.Column(db.Integer, primary_key = True)
	value = db.Column(db.String(150))
	num = db.Column(db.Integer, default=0)
	f_id = db.Column(db.Integer, db.ForeignKey('vote.id'))
	image = db.Column(db.String(10000))

db.create_all()

def create_plot(b):
	num = [x.num for x in b]
	name = [y.value for y in b]
	data = [go.Bar(x=name,y=num)]
	graphJSON = json.dumps(data,cls=plotly.utils.PlotlyJSONEncoder)

	return graphJSON

def sendMail(vote_id):
	data = Check.query.filter_by(v_id=vote_id).all()
	receptints = []
	for items in data:
		u = Users.query.filter_by(uname=items.username).all()
		receptints = [i.email for i in u]
	opt = Option.query.filter_by(f_id=vote_id).all()
	vote = Vote.query.filter_by(id=vote_id).first()
	max_vote = 0
	winner = ''
	for i in opt:
		if i.num > max_vote:
			max_vote = i.num
			winner = i.value
	SUBJECT = 'Voting Result'
	TEXT = f"Here is the result of the Voting\nTitle: {vote.title}\nWinner: {winner} vote count {max_vote}"
	message = "Subject: {}\n\n{}".format(SUBJECT, TEXT)
	server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
	server.ehlo()
	server.login('[email@example.com]', '[password]')
	server.sendmail('[email@example.com]', receptints, message)
	server.close()

with open('new.txt','r') as file:
	f = file.readlines()
	for line in f:
		data = line.split()
		user = Users.query.filter_by(uname=data[0]).first()
		if user:
			continue
		else:
			u = Users(uname=data[0],aadhar=data[1],email=data[2])
			db.session.add(u)
			db.session.commit()

@app.route('/',methods=['POST','GET'])
def index():
	if request.method == 'POST':
		u = Users.query.filter_by(uname=request.form['uname']).first()
		if u:
			if request.form['uname'] == u.uname and request.form['aadhar'] == u.aadhar:
				session['username'] = u.uname
				return redirect(url_for('polling',page=1))
			return render_template('index.html', msg="Invalid Credentials")
		else:
			return render_template('index.html',msg="User doesn't exist")
	return render_template("index.html")

#Route for admin
@app.route('/admin',methods=['POST','GET'])
def admin():
	if request.method == 'POST':
		if request.form['username'] == 'admin' and request.form['password'] == 'password':
			session['username'] = 'admin'
			return redirect(url_for('newvote'))
		else:
			return 'Invalid Password'
	return render_template("admin.html")

#Route for users to vote 
@app.route('/vote/<int:opt>/<int:v>',methods=['POST','GET'])
def vote(opt,v):
	if session['username']:
		option = Option.query.filter_by(id=opt).first()
		option.num +=1
		check = Check(username=session['username'],v_id=v)
		db.session.add(check)
		db.session.commit()
		return redirect(url_for('polling',page=v))
	return redirect(url_for('index'))

#New Vote Creation
@app.route('/newvote',methods=['POST','GET'])
def newvote():
	if session['username'] == 'admin':
		if request.method == 'POST':
			expiry = time.time() + int(request.form['time'])*86400
			vote = Vote(title=request.form['title'],duration=expiry)
			db.session.add(vote)
			db.session.commit()
			main = Vote.query.filter_by(title=request.form['title']).first()
			mail_time = int(request.form['time'])*86400
			t = Timer(mail_time, sendMail,[main.id])
			t.start()
			for i in range(int(request.form['num'])):
				if request.form[str(i)]:
					img = request.files['image-'+str(i)]
					img_data = base64.b64encode(img.read())
					image_data = img_data.decode('utf-8')
					opt = Option(value=request.form[str(i)],num=0,f_id=main.id,image=image_data)
					db.session.add(opt)
					db.session.commit()
				continue
			return redirect(url_for('newvote'))
		return render_template('newvote.html')
	return redirect(url_for('index'))

#Actual Voting
@app.route('/polling/<int:page>',methods=['POST','GET'])
def polling(page):
	if session['username']:
		main = Vote.query.filter_by(id=page).first()
		vote = Vote.query.all()
		opt = Option.query.all()
		user = Users.query.filter_by(uname=session['username']).first()
		if main:
			check = Check.query.filter_by(v_id=main.id).all()
			num = 0
			for i in check:
				if i.username == session['username']:
					num = 1
					break
			if time.time()>main.duration:
				return render_template('time.html',main=main,opt=opt,vote=vote)
			elif num==1:
				return render_template('test.html',main=main,opt=opt,vote=vote)
			return render_template('poll.html',opt=opt,main=main,vote=vote)
		else:
			return render_template('error.html',opt='',main='',vote='')
	return redirect(url_for('index'))

@app.route('/result')
def result():
	if session['username'] == 'admin':
		page = request.args.get('page',1,type=int)
		vote = Vote.query.paginate(page=page,per_page=1)
		opt = Option.query.filter_by(f_id=vote.items[0].id).all()
		title =  vote.items[0].title
		bar = create_plot(opt)
		return render_template('result.html',vote=vote,bar=bar,title=title)
	return redirect(url_for('index'))

#Logout Route
@app.route('/logout')
def logout():
	if session['username']:
		session['username'] = None
		return redirect(url_for('index'))
	return redirect(url_for('index'))

if __name__ == "__main__":
	app.secret_key = '7894645'
	app.run(debug=True)