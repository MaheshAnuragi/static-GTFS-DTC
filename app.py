from email import header
import json
from operator import mod, ne
import os
from pickle import LONG1
from sre_constants import SUCCESS
# from syslog import LOG_LOCAL1
import time
import hashlib
from ast import literal_eval
from xmlrpc.client import TRANSPORT_ERROR
from sqlalchemy import func, exists
import folium as folium
from folium import plugins
import numpy as np
from numpy.core.arrayprint import printoptions
import pandas as pd
from flask import Flask, abort, render_template, redirect, request, url_for, jsonify, session, flash, send_file
from flask_cors import CORS
from flask_marshmallow import Marshmallow
from flask_sqlalchemy import SQLAlchemy
from collections import defaultdict
from datetime import datetime, timedelta
from geopy.distance import distance
from flask_login import login_user, login_required, logout_user, LoginManager, UserMixin, current_user
import zipfile
import shutil
import math
import sqlite3
import gc

from tqdm import tqdm
from werkzeug.utils import secure_filename
from zipfile import ZipFile
from flask_migrate import Migrate
import csv
import datetime
from flask_socketio import SocketIO, emit

ALLOWED_EXTENSIONS = {'txt'}

app = Flask(__name__, static_folder='static')
socketio = SocketIO(app)
app.config['TEMPLATES_AUTO_RELOAD'] = True
SQLITE_DB = 'db.sqlite3'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(SQLITE_DB)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'super secret key'
app.config['USE_SESSSION_FOR_NEXT'] = True
db = SQLAlchemy(app)
migrate = Migrate(app, db)
ma = Marshmallow(app)
CORS(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please login to your account"


# all_routes_df = pd.read_csv('all_routes.csv', sep=';')

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    agency = db.Column(db.String(64), index=True, unique=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password = db.Column(db.String(64))
    all_routes = db.relationship('AllRoutes', cascade="all,delete", backref='user')
    routes = db.relationship('routes', cascade="all,delete", backref='user')
    stopTimes = db.relationship('stopTimes', cascade="all,delete", backref='user')
    stops = db.relationship('stops', cascade="all,delete", backref='user')
    trips = db.relationship('trips', cascade="all,delete", backref='user')


class trips(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.String(50), db.ForeignKey('all_routes.route_id', ondelete='CASCADE'))
    service_id = db.Column(db.String(50))
    trip_id = db.Column(db.String(50))
    speed = db.Column(db.String(20))
    freq = db.Column(db.String(20))
    shape_id = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    stop_times = db.relationship('stopTimes', cascade='all, delete', backref='trips')


class stops(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stop_id = db.Column(db.String(50))
    stop_code = db.Column(db.String(50))
    stop_name = db.Column(db.String(100))
    stop_lat = db.Column(db.String(50))
    stop_lon = db.Column(db.String(50))
    zone_id = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class stopTimes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.String(50), db.ForeignKey('trips.trip_id', ondelete='CASCADE'))
    arrival_time = db.Column(db.String(50))
    departure_time = db.Column(db.String(50))
    stop_id = db.Column(db.String(50))
    stop_sequence = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class routes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.String(50))
    route_id = db.Column(db.String(50), db.ForeignKey('all_routes.route_id', ondelete='CASCADE'))
    route_long_name = db.Column(db.String(50))
    route_short_name = db.Column(db.String(50))
    route_type = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class AllRoutes(db.Model):  # model for db
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.String(70))
    route_name = db.Column(db.String(50))
    agency_id = db.Column(db.String(50))
    status = db.Column(db.Integer)  # 2 (running) or 1 (completed) or 0 (incomplete)
    stop_details = db.Column(db.String)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    routes = db.relationship('routes', cascade="all, delete", backref='all_routes')
    trips = db.relationship('trips', cascade="all, delete", backref='all_routes')

    def __init__(self, route_id, route_name, agency_id, status, stop_details, user_id):
        self.route_id = route_id
        self.route_name = route_name
        self.agency_id = agency_id

        self.status = status
        self.stop_details = stop_details
        self.user_id = user_id


with app.app_context():
    db.create_all()
global all_stops_deleted
all_stops_deleted = False


@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    if request.method == 'POST':
        agency = request.form.get('agency')
        username = request.form.get('username')
        password = request.form.get('password')
        print("in login page ", username, password, agency)

        obj1 = User(agency=agency, username=username, password=password)
        db.session.add(obj1)
        db.session.commit()
        # make_all_routes(username, agency)
        result = User.query.all()
        print(result)
        if os.path.exists(f'data/{agency}/{username}/Imported_files'):
            flash("user is created and folder is already exists")
            return redirect(url_for('login'))

        else:
            os.makedirs(f'data/{agency}/{username}/Imported_files')
            os.makedirs(f'data/{agency}/{username}/Exported_files')

        flash(f"user is created ,create DB for new user")

        return redirect(url_for('login'))


@app.route('/delete_user', methods=['GET', 'POST'])
def delete_user():
    if request.method == 'POST':
        agency = request.form.get('agency')
        username = request.form.get('username')

        user_exist = User.query.filter_by(agency=agency, username=username).first()
        print(user_exist)
        if user_exist is None:
            return "User does not exist !!"
        else:
            print("user is existed ", user_exist)

            db.session.delete(user_exist)

            db.session.commit()
            flash("User is deleted !!")
            return redirect(url_for('admin'))


def make_all_routes(username, agency):
    # db.session.query(AllRoutes).delete()   
    print(username, agency)

    # -------------------------------------------------
    user = User.query.filter_by(username=username, agency=agency).first()
    print("user details: ", user.username, user.id)

    # filling a trip DB
    existed_data_trips = trips.query.filter_by(user_id=user.id).all()
    if existed_data_trips != []:
        trips.query.filter_by(user_id=user.id).delete()
    fill_trips(user.id, user.username, agency)

    # filling a routes DB
    existed_data_routes = routes.query.filter_by(user_id=user.id).all()
    if existed_data_routes != []:
        routes.query.filter_by(user_id=user.id).delete()
    fill_routes(user.id, user.username, agency)

    # filling a stopTimes DB
    existed_data_stopTimes = stopTimes.query.filter_by(user_id=user.id).all()
    if existed_data_stopTimes != []:
        stopTimes.query.filter_by(user_id=user.id).delete()
    fill_stopTimes(user.id, user.username, agency)

    # filling a stops DB
    existed_data_stops = stops.query.filter_by(user_id=user.id).all()
    if existed_data_stops != []:
        stops.query.filter_by(user_id=user.id).delete()
    fill_stops(user.id, user.username, agency)

    existed_data_allRoute = AllRoutes.query.filter_by(user_id=user.id).all()
    if existed_data_allRoute != []:
        existed_data_allRoute = AllRoutes.query.filter_by(user_id=user.id).delete()

    # routes_df = pd.read_csv(f'data/{user.username}/new_routes.txt',dtype = {'route_id': str, 'agency_id': str, 'route_short_name': str, 'route_long_name': str},converters={'route_id': str.strip, 'agency_id': str.strip, 'route_short_name': str.strip, 'route_long_name': str.strip})

    routes_data = routes.query.filter_by(user_id=user.id).all()

    routes_df = pd.DataFrame(
        [(route.route_id, route.agency_id, route.route_short_name, route.route_long_name) for route in routes_data],
        columns=['route_id', 'agency_id', 'route_short_name', 'route_long_name'])

    # if agency is not None:
    #     routes_df = routes_df[routes_df.agency_id == agency]
    #     # print("routes df after agency: \n",routes_df)

    trips_data = trips.query.filter_by(user_id=user.id).all()

    trips_df = pd.DataFrame([(trip.route_id, trip.trip_id) for trip in trips_data],
                            columns=['route_id', 'trip_id'])

    stops_data = stops.query.filter_by(user_id=user.id).all()

    stops_df = pd.DataFrame([(stop.stop_id, stop.stop_name) for stop in stops_data],
                            columns=['stop_id', 'stop_name'])

    stopTimes_data = stopTimes.query.filter_by(user_id=user.id).all()

    stop_times_df = pd.DataFrame([(stopTimes.stop_id, stopTimes.trip_id) for stopTimes in stopTimes_data],
                                 columns=['stop_id', 'trip_id'])

    # trips_df = pd.read_csv(f'data/{username}/new_trips.txt',dtype={'trip_id':str,'route_id':str},converters={'trip_id':str.strip,'route_id':str.strip})
    # stops_df = pd.read_csv(f'data/{username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip})
    # stop_times_df = pd.read_csv(f'data/{username}/new_stop_times.txt', dtype={"stop_id": str,"trip_id":str},converters={"stop_id": str.strip,"trip_id":str.strip})
    if "fare_stage" not in stop_times_df.columns:
        stop_times_df['fare_stage'] = np.full(len(stop_times_df), '0')

    route_id_name_dict = pd.Series(data=routes_df.route_long_name.values, index=routes_df.route_id).to_dict()

    # print('route_id_name_dict \n',route_id_name_dict)

    progress = 0  # Initialize progress
    total_routes = len(route_id_name_dict)

    model_list = list()
    for i, (route_id, route_name) in enumerate(tqdm(route_id_name_dict.items())):

        # Calculate progress as a percentage
        progress = int((i + 1) / total_routes * 100)
        
        # Send progress update to the frontend
        socketio.emit('update_progress', {'progress': progress})

        # print("route-d -----> ",route_id,"type : ",type(route_id))
        route_stop_details = list()

        if route_id not in trips_df.route_id.values:
            print("-----not present ---", route_id)
            continue

        route_trip = trips_df[trips_df.route_id == route_id].trip_id.values[0]

        route_stops = stop_times_df[stop_times_df.trip_id == route_trip][['stop_id', 'fare_stage']]

        route_stop_ids = route_stops.stop_id.values
        route_stop_fare_stages = route_stops.fare_stage.values
        # print("len of fair stage -->",len(route_stop_fare_stages),"    "," len of stop id = ",len(route_stop_ids))

        route_stops_df = stops_df.set_index('stop_id').loc[route_stop_ids].reset_index(inplace=False)[
            ['stop_id']]

        # print("route_stops_df : \n",route_stops_df)
        route_stops_df['fare_stage'] = route_stop_fare_stages
        route_stop_details.append(route_stops_df.values.tolist())
        status = 1

        user_id = user.id
        if agency is None:
            agency = user.agency
        agency_id = agency
        all_routes_obj = AllRoutes(route_id, route_name, agency_id, status, str(route_stop_details[0]), user_id)
        model_list.append(all_routes_obj)
    db.session.add_all(model_list)
    db.session.commit()
    del routes_df, trips_df, stops_df, stop_times_df


# -----------filling a db via imported files------------

def fill_stops(user_id, user_username, agency):
    file_path = f'data/{agency}/{user_username}/Imported_files/stops.txt'
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            reader = csv.DictReader(file)
            
            total_rows = sum(1 for row in reader)  # Count the total number of rows
            file.seek(0)  # Reset the file pointer to the beginning
            progress = 0  # Initialize progress
            processed_rows = 0  # Initialize processed rows count

            # Skip the header row
            next(reader)
            for row in reader:
                processed_rows += 1
                progress = int((processed_rows / total_rows) * 100)
                print('fill_stops',progress)
                # Send progress update to the frontend
                socketio.emit('update_progress', {'progress': progress})

                new_stops = stops(
                    stop_id=row['stop_id'],
                    stop_code=row['stop_code'],
                    stop_name=row['stop_name'],
                    stop_lat=row['stop_lat'],
                    stop_lon=row['stop_lon'],
                    zone_id=row['zone_id'] if "zone_id" in row else "",
                    user_id=user_id,
                )
                db.session.add(new_stops)

            db.session.commit()


def fill_stopTimes(user_id, user_username, agency):
    file_path = f'data/{agency}/{user_username}/Imported_files/stop_times.txt'
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            reader = csv.DictReader(file)

            total_rows = sum(1 for row in reader)  # Count the total number of rows
            file.seek(0)  # Reset the file pointer to the beginning
            progress = 0  # Initialize progress
            processed_rows = 0  # Initialize processed rows count

            # Skip the header row
            next(reader)
            for row in reader:
                processed_rows += 1
                progress = int((processed_rows / total_rows) * 100)
                print('fill_stopTimes',progress)
                # Send progress update to the frontend
                socketio.emit('update_progress', {'progress': progress})

                new_stopTimes = stopTimes(
                    trip_id=row['trip_id'],
                    arrival_time=row['arrival_time'],
                    departure_time=row['departure_time'],
                    stop_id=row['stop_id'],
                    stop_sequence=row['stop_sequence'],
                    user_id=user_id,
                )
                db.session.add(new_stopTimes)

            db.session.commit()


def fill_routes(user_id, user_username, agency):
    file_path = f'data/{agency}/{user_username}/Imported_files/routes.txt'
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            reader = csv.DictReader(file)

            total_rows = sum(1 for row in reader)  # Count the total number of rows
            file.seek(0)  # Reset the file pointer to the beginning
            progress = 0  # Initialize progress
            processed_rows = 0  # Initialize processed rows count

            # Skip the header row
            next(reader)
            for row in reader:
    
                processed_rows += 1
                progress = int((processed_rows / total_rows) * 100)
                print('fill_routes',progress)
                # Send progress update to the frontend
                socketio.emit('update_progress', {'progress': progress})

                new_routes = routes(
                    agency_id=row['agency_id'],
                    route_id=row['route_id'],
                    route_long_name=row['route_long_name'],
                    route_short_name=row['route_short_name'],
                    route_type=row['route_type'],
                    user_id=user_id,
                )
                db.session.add(new_routes)

            db.session.commit()


def fill_trips(user_id, user_username, agency):
    file_path = f'data/{agency}/{user_username}/Imported_files/trips.txt'
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            reader = csv.DictReader(file)

            total_rows = sum(1 for row in reader)  # Count the total number of rows
            file.seek(0)  # Reset the file pointer to the beginning
            progress = 0  # Initialize progress
            processed_rows = 0  # Initialize processed rows count

            # Skip the header row
            next(reader)
            for row in reader:
                
                processed_rows += 1
                progress = int((processed_rows / total_rows) * 100)
                print('fill_trips',progress)
                # Send progress update to the frontend
                socketio.emit('update_progress', {'progress': progress})

                speed = row.get('speed', '15')
                freq = row.get('freq', '10')
                new_trip = trips(
                    route_id=row['route_id'],
                    service_id=row['service_id'],
                    trip_id=row['trip_id'],
                    shape_id=row['shape_id'],
                    speed=speed,
                    freq=freq,
                    user_id=user_id,
                )
                db.session.add(new_trip)

            db.session.commit()


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        print("in login page ", username)

        user = User.query.filter_by(username=username).first()
        if user:
            if (user.password == password):
                login_user(user, remember=True)
                if 'next' in session:
                    next = session['next']
                    print("in line 178\n", next)
                if next != None:
                    return redirect(next)
                else:
                    return redirect(url_for('index'))
            else:
                error = "Incorrect password, try again !!"
                print('Incorrect password, try again.')
                return render_template('views/login.html', error=error)
        else:
            error = "User Does Not Exist"
            print('user does not exist.')
            return render_template('views/login.html', error=error)

    session['next'] = request.args.get('next')
    print("****in line 187\n*****", session['next'])

    return render_template('views/login.html')


@app.route('/adminMain', methods=['GET', 'POST'])
def adminMain():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        print("in login page ", username)
        if(username == 'admin' and password == 'admin'):
            return render_template('views/admin.html')
        else:
            return "Invalid username or password"
    return render_template('views/adminMain.html')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    return "the current user is " + current_user.username


def plot(route_id, user_id, username):
    new_var = str(user_id) + "_" + str(route_id)

    print("\n---in plot fn --- dict item : ", new_var)
    global routes_stop

    db_response = db.session.query(AllRoutes).filter_by(route_id=route_id, user_id=user_id).all()[0]
    stop_details = np.array(literal_eval(db_response.stop_details))

    routes_stop[new_var] = literal_eval(db_response.stop_details)

    if len(stop_details) == 0:
        points = []
        response = []
        m = folium.Map(location=[28.630691, 77.217648], zoom_start=11)

    else:
        stops_data = stops.query.filter_by(user_id=user_id).all()

        stops_df = pd.DataFrame(
            [(stop.stop_id, stop.stop_name, float(stop.stop_lat), float(stop.stop_lon)) for stop in stops_data],
            columns=['stop_id', 'stop_name', 'stop_lat', 'stop_lon'])

        route_stops_df = stops_df.set_index('stop_id').loc[stop_details[:, 0]].reset_index(inplace=False)

        points = route_stops_df[['stop_lat', 'stop_lon']].values.tolist()
        response = route_stops_df.values.tolist()

        m = folium.Map(location=points[0], zoom_start=11)

        for k in range(len(points)):
            # Create a custom DivIcon with both the blue icon and the label
            custom_icon = folium.DivIcon(html=f'''
                <div>
                    <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png" style="width: 26px; height: 38px; margin-top: -50px;">
                    <div style="position: absolute; top: 110%; left: 110%; transform: translate(-50%, -50%); text-align: center;margin-top: -32px; font-weight: bold; background-color: #2C83CB; color: white; padding: 1px; border-radius: 5px;">{k+1}</div>
                </div>
            ''')
            
            # Create a marker with the custom DivIcon
            marker = folium.Marker(
                location=points[k],
                popup=response[k][1],
                tooltip=response[k][1],
                icon=custom_icon
            )
            
            marker.add_to(m)

        # Create ant path
        ant_path = plugins.AntPath(points, color='blue', weight=5)

        # Add ant path to the map
        ant_path.add_to(m)

        bounds = ant_path.get_bounds()
        m.fit_bounds(bounds)

    route_name = db_response.route_name

    print("\n--------in plot fn-------\n", routes_stop[new_var])

    return m._repr_html_(), response, route_name


def get_route_info(route_id, user_id, username):
    new_var = str(user_id) + "_" + str(route_id)
    global routes_stop

    db_response = db.session.query(AllRoutes).filter_by(route_id=route_id, user_id=user_id).first()
    stop_details = np.array(literal_eval(db_response.stop_details))
    routes_stop[new_var] = literal_eval(db_response.stop_details)

    if len(stop_details) == 0:
        points = []
        response = []
    else:
        stops_data = stops.query.filter_by(user_id=user_id).all()
        stops_df = pd.DataFrame(
            [(stop.stop_id, stop.stop_name, float(stop.stop_lat), float(stop.stop_lon)) for stop in stops_data],
            columns=['stop_id', 'stop_name', 'stop_lat', 'stop_lon'])

        # stops_df = pd.read_csv(f'data/{username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip})
        db_response = db.session.query(AllRoutes).filter_by(route_id=route_id, user_id=user_id).all()[0]
        # new_list = routes_stop[new_var]

        # k = [str(i[0]) for i in new_list]
        # route_stops_df = stops_df.set_index('stop_id').loc[k].reset_index(inplace=False)[
        # ['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]
        # list1 = np.array(route_stops_df.values.tolist())

        route_stops_df = stops_df.set_index('stop_id').loc[stop_details[:, 0]].reset_index(inplace=False)

        # points = list1[:, [0,2, 3]].astype(float).tolist()
        # points = list1[:, [2, 3]].astype(float).tolist()

        points = route_stops_df[['stop_lat', 'stop_lon']].values.tolist()
        response = route_stops_df.values.tolist()

        for i in range(len(response)):
            points[i].insert(0, response[i][0])

        # response = list1[:, 0:5].tolist()

    route_name = db_response.route_name

    return points, response, route_name, len(points)


# @app.route('/')
# def hello_world():
#     return 'Hello World!'
global routes_stop
routes_stop = {}


@app.route("/", methods=["GET", 'POST'])
@login_required
def index():
    # experiment()
    # return render_template('views/new2.html')

    print("*******the current user in index function ", current_user.id)

    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)
    print("-------the logged in  user is----", current_user.username)
    # create new_list as empty as the home page started and it store the stop details and get modified  whenever add,delete,update are perform
    # all_routes = db.session.query(AllRoutes).all()
    routes_list = dict()

    print("user.id--------------", user.id)
    # all_routes = db.session.query(AllRoutes).filter_by(user_id=user.id).all()
    all_routes = AllRoutes.query.filter_by(user_id=current_user.id).all()
    for route in all_routes:
        routes_list[route.route_id] = route.route_name

    return render_template('views/new.html', stops_list=routes_list, user_id=user.id, agency=user.agency)


# -------stopView-------
@app.route("/stops_view/<int:user_id>", methods=['GET', 'POST'])
@login_required
def stops_view(user_id):
    data_list = []

    stop_records = stops.query.filter_by(user_id=user_id).all()

    for record in stop_records:
        data_list.append([record.stop_id, record.stop_name, record.stop_lat, record.stop_lon])

    return render_template('views/stopView.html', user_id=user_id, response=data_list)


@app.route("/delete_stop/<stop_id>", methods=['GET', 'POST'])
@login_required
def delete_stop(stop_id):
    if request.method == 'POST':
        stop = stops.query.filter_by(stop_id=stop_id, user_id=current_user.id).first()
        db.session.delete(stop)
        db.session.commit()

        # Query the routes table to get all route_id values
        route_data = AllRoutes.query.filter(
            AllRoutes.stop_details.like(f"%'{stop_id}'%")
        ).all()

        route_id_list = [route.route_id for route in route_data]

        # Print the list of route_ids
        print(route_id_list)
        for route_id in route_id_list:
            delete_Allstop(route_id, stop_id)
            all_routes = AllRoutes.query.filter_by(route_id=route_id).first()
            if all_routes.status == 0:
                trip_ids = trips.query.filter_by(route_id=route_id, user_id=current_user.id).all()
                trip_id_list = [trip.trip_id for trip in trip_ids]
                trip_freq = [trip.service_id for trip in trip_ids]
                trip_speed = [trip.speed for trip in trip_ids]

                # Delete each trip ID
                for trip in trip_ids:
                    db.session.delete(trip)

                print(trip_id_list)
                print(trip_freq)
                print(trip_speed)

                recreate_trips(trip_id_list, trip_freq, trip_speed, route_id)

                print("Trip has been Updated!")

                all_routes.status = 1

                db.session.commit()

        flash("Stop has been Deleted!")

    return redirect(url_for('stops_view', user_id=current_user.id))


def recreate_trips(trip_id_list, trip_freq, trip_speed, route_id):
    folium_map, response, route_name = plot(route_id, current_user.id, current_user.username)

    if len(response) == 0:
        return

    for i in range(len(trip_id_list)):

        tripID = trip_id_list[i]
        speed = trip_speed[i]
        frequency = trip_freq[i]
        converted_time = tripID.split("_", 1)[1]
        trip_time = converted_time.replace("_", ":")
        print(converted_time)
        print(trip_time)

        # Check if the trip_time already exists for the given route_id and user_id
        existing_trip = trips.query.filter_by(route_id=route_id, user_id=current_user.id, trip_id=tripID).first()
        if existing_trip:
            # Update the existing trip_time entry
            existing_trip.speed = speed
            existing_trip.freq = frequency
        else:
            # Create a new instance of allTrips and store the values
            trip = trips(route_id=route_id, freq=frequency, service_id=1, trip_id=tripID, speed=speed,
                         user_id=current_user.id)
            db.session.add(trip)
            db.session.commit()

        # creating stops-times table
        # first trip-ID with stop seq. filling bcz have same arrival-departure time at first time.
        # filling a stopTimes DB
        arrival_time = trip_time + ':00'
        departure_time = trip_time + ':00'
        stop_id = response[0][0]
        stop_sequence = 0
        existed_data_stopTimes = stopTimes.query.filter_by(user_id=current_user.id, trip_id=tripID,
                                                           arrival_time=arrival_time, departure_time=departure_time,
                                                           stop_id=stop_id, stop_sequence=stop_sequence).all()
        print("------------existed_data_stopTimes----------")
        print(existed_data_stopTimes)
        if existed_data_stopTimes == []:
            existed_data_stopTimes = stopTimes(user_id=current_user.id, trip_id=tripID, arrival_time=arrival_time,
                                               departure_time=departure_time, stop_id=stop_id,
                                               stop_sequence=stop_sequence)
            db.session.add(existed_data_stopTimes)

        for x in range(1, len(response)):  # in response i have stop_id and stop_name at 0 and 1 indexes
            stop1 = stops.query.filter_by(user_id=current_user.id, stop_id=response[x - 1][0]).first()
            stop2 = stops.query.filter_by(user_id=current_user.id, stop_id=response[x][0]).first()

            lat1 = stop1.stop_lat
            lat2 = stop2.stop_lat
            lon1 = stop1.stop_lon
            lon2 = stop2.stop_lon

            # Define the coordinates as tuples
            coord1 = (lat1, lon1)
            coord2 = (lat2, lon2)

            # Calculate the distance between the coordinates
            distanc = distance(coord1, coord2).kilometers

            calcTime = (float(distanc) / float(speed)) * 60

            # calculate time with calcTime with departure time
            arrival_time = addFormateTime(departure_time, calcTime)
            departure_time = arrival_time

            data_stopTimes = stopTimes.query.filter_by(user_id=current_user.id, trip_id=tripID,
                                                       arrival_time=arrival_time, departure_time=departure_time,
                                                       stop_id=response[x][0], stop_sequence=x).all()
            if data_stopTimes == []:
                # The record doesn't exist, so add it to the `stopTimes` table
                data_stopTimes = stopTimes(user_id=current_user.id, trip_id=tripID, arrival_time=arrival_time,
                                           departure_time=departure_time, stop_id=response[x][0], stop_sequence=x)
                db.session.add(data_stopTimes)

        db.session.commit()


def delete_Allstop(route_id, stop_id):
    # Assuming you have an instance of AllRoutes
    all_routes = AllRoutes.query.filter_by(route_id=route_id).first()

    # Check if the instance exists
    if all_routes:
        # Access the stop_details attribute
        stop_details = literal_eval(all_routes.stop_details)

        # Specify the stop_id to remove
        stop_id_to_remove = stop_id

        prev_len = len(stop_details)

        # Iterate over the stop_details and remove the sublist with the specified stop_id
        stop_details = [stop for stop in stop_details if stop[0] != stop_id_to_remove]

        curr_len = len(stop_details)

        if (prev_len != curr_len):
            all_routes.status = 0

        # Update the stop_details attribute with the modified list
        all_routes.stop_details = str(stop_details)

        # Commit the changes to the database
        db.session.commit()

        # Print the updated stop_details
        print(all_routes.stop_details)
    else:
        print("No AllRoutes instance found for the specified criteria.")


@app.route("/stops_change", methods=['GET', 'POST'])
@login_required
def stops_change():
    if request.method == 'POST':
        referrer = "stop"
        request_referrer = request.referrer
        if request_referrer.__contains__("route"):
            referrer = "route"
        stop_id = request.form.get('stop_id2') if referrer == "stop" else request.form.get('stop_id3')
        stop_lat = request.form.get('lat_name2') if referrer == "stop" else request.form.get('lat_name3')
        stop_lon = request.form.get('long_name2') if referrer == "stop" else request.form.get('long_name3')
        stop_name = request.form.get('stop_name2') if referrer == "stop" else request.form.get('stop_name3')
        stop_record = stops.query.filter_by(user_id=current_user.id, stop_id=stop_id).first()

        if stop_record:
            stop_record.stop_lat = stop_lat
            stop_record.stop_lon = stop_lon
            stop_record.stop_name = stop_name
            db.session.commit()
            flash("Changes have been updated!")
        else:
            # Handle the case when the record is not found
            flash("Stop record not found!")

        if referrer == "route":
            return redirect(request_referrer)
    return redirect(url_for('stops_view', user_id=current_user.id))


@app.route("/stops_add", methods=['GET', 'POST'])
@login_required
def stops_add():
    if request.method == 'POST':
        stop_id_option = request.form['set_stop_id']
        new_stop_id = request.form['new_stop_id']
        stop_lat = request.form.get('lat_name')
        stop_lon = request.form.get('long_name')
        stop_name = request.form.get('stop_name')

        # Check if a stop with the same lat and lon exists
        stop_exists = db.session.query(exists().where((stops.stop_lat == stop_lat) & (stops.stop_lon == stop_lon))).scalar()

        if stop_exists:
            flash('A stop with the same coordinates already exists.')
            return redirect(url_for('stops_view', user_id=current_user.id))

        stop_id = 0  # by default

        if stop_id_option == 'default_id':

            stop_id = generate_hexcode(stop_lat, stop_lon, stop_name)

            flash("Stop has been added!")
        else:
            stop_id_exists = db.session.query(exists().where(stops.stop_id == new_stop_id)).scalar()

            if stop_id_exists:
                # Show an alert message that the stop_id already exists
                flash('Stop ID already exists. Please enter a different stop ID.')
                return redirect(url_for('stops_view', user_id=current_user.id))
            else:
                stop_id = new_stop_id

        new_stop = stops(user_id=current_user.id, stop_id=stop_id, stop_lat=stop_lat, stop_lon=stop_lon,
                         stop_name=stop_name)
        db.session.add(new_stop)
        db.session.commit()

    return redirect(url_for('stops_view', user_id=current_user.id))


def generate_hexcode(stop_lat, stop_lon, stop_name):
    input_string = bytes(f"{stop_lat}{stop_lon}{stop_name}".lower(), encoding='utf-8')
    hash_object = hashlib.sha256(input_string)
    hex_dig = hash_object.hexdigest()[:8].upper()
    return hex_dig


@app.route("/view_route/<route_id>", methods=['GET', 'POST'])
@login_required
def view_route(route_id):
    global routes_stop

    print("----------in view_route", current_user.id)
    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)

    new_var = str(user.id) + "_" + str(route_id)

    routes_stop[new_var] = []

    print(new_var, routes_stop)
    folium_map, response, route_name = plot(route_id, user.id, user.username)
    # return 'hello ' + str(route_id)
    print(route_id)
    print("type of route id", type(route_id))

    if request.method == 'POST':
        user = User.query.filter_by(id=current_user.id).first()
        speed = request.form.get('speed-input')
        frequency = request.form.get('freq-input')
        start_time = request.form.get('start-input')
        end_time = request.form.get('end-input')

        if (len(response) == 0):
            flash("Atleast add one Stop!")
            return redirect(url_for('view_route', route_id=route_id))

        if not end_time:
            end_time = start_time

        route_id = request.form.get('route_id')

        start_hour = int(start_time.split(':')[0])
        start_minute = int(start_time.split(':')[1])

        end_hour = int(end_time.split(':')[0])
        end_minute = int(end_time.split(':')[1])

        current_hour = start_hour
        current_minute = start_minute

        Times = []

        while current_hour < end_hour or (current_hour == end_hour and current_minute <= end_minute):
            time = str(current_hour).zfill(2) + ':' + str(current_minute).zfill(2)

            # Add the time to the set
            Times.append(time)

            # Update currentHour and currentMinute
            current_minute += int(frequency)
            if current_minute >= 60:
                current_minute %= 60
                current_hour += 1

        for trip_time in Times:
            converted_time = trip_time.replace(":", "_")
            tripID = route_id + '_' + converted_time

            # Check if the trip_time already exists for the given route_id and user_id
            existing_trip = trips.query.filter_by(route_id=route_id, user_id=current_user.id, trip_id=tripID).first()
            if existing_trip:
                # Update the existing trip_time entry
                existing_trip.speed = speed
                existing_trip.freq = frequency
            else:
                # Create a new instance of allTrips and store the values
                trip = trips(route_id=route_id, freq=frequency, service_id=1, trip_id=tripID, speed=speed,
                             user_id=user.id)
                db.session.add(trip)
                db.session.commit()

            # creating stops-times table
            # first trip-ID with stop seq. filling bcz have same arrival-departure time at first time.
            # filling a stopTimes DB
            arrival_time = trip_time + ':00'
            departure_time = trip_time + ':00'
            stop_id = response[0][0]
            stop_sequence = 0
            existed_data_stopTimes = stopTimes.query.filter_by(user_id=user.id, trip_id=tripID,
                                                               arrival_time=arrival_time, departure_time=departure_time,
                                                               stop_id=stop_id, stop_sequence=stop_sequence).all()
            print("------------existed_data_stopTimes----------")
            print(existed_data_stopTimes)
            if existed_data_stopTimes == []:
                existed_data_stopTimes = stopTimes(user_id=user.id, trip_id=tripID, arrival_time=arrival_time,
                                                   departure_time=departure_time, stop_id=stop_id,
                                                   stop_sequence=stop_sequence)
                db.session.add(existed_data_stopTimes)

            for x in range(1, len(response)):  # in response i have stop_id and stop_name at 0 and 1 indexes
                stop1 = stops.query.filter_by(user_id=user.id, stop_id=response[x - 1][0]).first()
                stop2 = stops.query.filter_by(user_id=user.id, stop_id=response[x][0]).first()

                lat1 = stop1.stop_lat
                lat2 = stop2.stop_lat
                lon1 = stop1.stop_lon
                lon2 = stop2.stop_lon

                # Define the coordinates as tuples
                coord1 = (lat1, lon1)
                coord2 = (lat2, lon2)

                # Calculate the distance between the coordinates
                distanc = distance(coord1, coord2).kilometers

                calcTime = (float(distanc) / float(speed)) * 60

                # calculate time with calcTime with departure time
                arrival_time = addFormateTime(departure_time, calcTime)
                departure_time = arrival_time

                data_stopTimes = stopTimes.query.filter_by(user_id=user.id, trip_id=tripID, arrival_time=arrival_time,
                                                           departure_time=departure_time, stop_id=response[x][0],
                                                           stop_sequence=x).all()
                if data_stopTimes == []:
                    # The record doesn't exist, so add it to the `stopTimes` table
                    data_stopTimes = stopTimes(user_id=user.id, trip_id=tripID, arrival_time=arrival_time,
                                               departure_time=departure_time, stop_id=response[x][0], stop_sequence=x)
                    db.session.add(data_stopTimes)

            db.session.commit()
        flash("Trips has been created!")

    # Get all the allTrips records with the specified route_id
    alltrips = trips.query.filter_by(route_id=route_id, user_id=current_user.id).order_by(trips.trip_id).all()

    # Extract the trip_time values into a list
    # trip_times = [trip.trip_id[-5:].replace("_", ":") for trip in alltrips]
    trip_times = [trip.trip_id for trip in alltrips]

    print(973,trip_times)

    return render_template('views/view.html', map=folium_map, response=response, trip_times=trip_times,
                           route_name=route_name, route_id=route_id, current_user=current_user.id)


def addFormateTime(departure_time, calc_time):
    # Convert departure_time to datetime object
    departure_datetime = datetime.datetime.strptime(departure_time, "%H:%M:%S")

    # Convert calc_time to timedelta object
    calc_timedelta = datetime.timedelta(minutes=calc_time)

    # Add calc_timedelta to departure_datetime
    result_datetime = departure_datetime + calc_timedelta

    # Convert result_datetime back to string in the format HH:MM:SS
    result_departure_time = result_datetime.strftime("%H:%M:%S")

    return result_departure_time


@app.route("/show_time_table/<route_id>/<trip_time>/<int:current_user>", methods=['POST'])
@login_required
def show_time_table(route_id, trip_time, current_user):
    # Find the trip record with the specified route_id, trip_id, and current_user
    # converted_time = trip_time.replace(":", "_")
    # tripID = route_id + '_' + converted_time
    print('------tripID----')
    print(trip_time)

    data_list = []
    # Find the trip records with the specified tripID
    trip_records = stopTimes.query.filter_by(trip_id=trip_time, user_id=current_user).all()
    print('------trip_records----')
    print(trip_records)
    # Extract the relevant data from each trip record and append it to the list
    for record in trip_records:
        stop_id = record.stop_id
        stop_name = stops.query.filter_by(stop_id=stop_id, user_id=current_user).first().stop_name

        data = {
            'arrival_time': record.arrival_time,
            'departure_time': record.departure_time,
            'stop_id': stop_id,
            'stop_name': stop_name,
            'stop_sequence': record.stop_sequence
        }
        data_list.append(data)

    # Convert the data_list to a JSON response
    response = jsonify(data_list)

    return response
    # Redirect to the view_route page after deletion
    # return redirect(url_for('view_route', route_id=route_id))


@app.route("/delete_trip/<route_id>/<trip_time>/<int:current_user>", methods=['POST'])
@login_required
def delete_trip(route_id, trip_time, current_user):
    # Find the trip record with the specified route_id, trip_id, and current_user
    converted_time = trip_time.replace(":", "_")
    tripID = route_id + '_' + converted_time
    trip = trips.query.filter_by(route_id=route_id, trip_id=tripID, user_id=current_user).first()
    data_stopTimes = stopTimes.query.filter_by(user_id=current_user, trip_id=tripID).all()
    if trip:
        db.session.delete(trip)

    if data_stopTimes:
        for data in data_stopTimes:
            db.session.delete(data)
    db.session.commit()

    # Redirect to the view_route page after deletion
    return redirect(url_for('view_route', route_id=route_id))


@app.route('/edit-route/<route_id>')
@login_required
def edit_route(route_id):
    # print(route_id)
    print("----------in edit_route", current_user.id)
    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)
    points, response, route_name, points_len = get_route_info(route_id, user.id, user.username)
    print('----points----')
    print(points)
    # stops_df = pd.read_csv(f'data/{user.username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip})
    stops_data = stops.query.filter_by(user_id=current_user.id).all()
    # print(stops_df.set_index('stop_id').T.to_dict('list'))
    # dict to fetch all the stop details
    print("response\n", response)
    # stops_dict = dict([(i,[i,a,b,c ]) for i, a,b,c in zip(stops_df.stop_id, stops_df.stop_name,stops_df.stop_lat,stops_df.stop_lon)])
    stops_dict = {stop.stop_id: [stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon] for stop in stops_data}
    return render_template('views/edit_route.html', response=response, points=points, route_name=route_name,
                           route_id=route_id, stops_dict=stops_dict, points_len=points_len)


# --------------------delete stop function-------------------------------------------------------------------
@app.route('/delete/<route_id>/<stop_id>')
@login_required
def delete(route_id, stop_id):
    user = User.query.filter_by(id=current_user.id).first()

    login_user(user)

    db_response = db.session.query(AllRoutes).filter_by(route_id=route_id, user_id=user.id).first()
    route_name = db_response.route_name
    stops_data = stops.query.filter_by(user_id=current_user.id).all()
    # stops_df = pd.read_csv(f'data/{user.username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip})
    stops_df = pd.DataFrame([(stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon) for stop in stops_data],
                            columns=['stop_id', 'stop_name', 'stop_lat', 'stop_lon'])

    new_var = str(user.id) + "_" + str(route_id)

    """[summary]

    Args:
    
        route_id ([type]): [description]
        stop_name ([type]): [description]

    Returns:
        [type]: [description]
        
    """

    # global route_name

    # global new_list

    global all_stops_deleted

    global routes_stop

    new_list = routes_stop[new_var]

    if len(new_list) == 0:
        routes_stop[new_var] = literal_eval(db_response.stop_details)  # fetch stop details
        new_list = routes_stop[new_var]

    print(new_list)
    print("\n\ndelete stop : ", stop_id)
    for i, x in enumerate(new_list):
        if stop_id == x[0]:
            print(i, x)
            sno = i
            break

    k = new_list.pop(sno)  # pop stop name using index number
    print("\n----------list after delete---------", new_list)
    print()

    if len(new_list) == 0:
        points = []
        response = []
        all_stops_deleted = True
    else:

        k = [str(i[0]) for i in new_list]
        route_stops_df = stops_df.set_index('stop_id').loc[k].reset_index(inplace=False)[
            ['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]
        list1 = np.array(route_stops_df.values.tolist())

        # points = list1[:, [0,2, 3]].astype(float).tolist()
        points = list1[:, [2, 3]].astype(float).tolist()

        for i in range(len(list1)):
            points[i].insert(0, list1[i][0])

        # points_len= len(points)
        response = list1[:, 0:5].tolist()

    # stops_dict = dict([(i,[i,a,b,c ]) for i, a,b,c in zip(stops_df.stop_id, stops_df.stop_name,stops_df.stop_lat,stops_df.stop_lon)]) #dict to fetch all the stop details
    stops_dict = {stop.stop_id: [stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon] for stop in stops_data}
    routes_stop[new_var] = new_list

    # in route stop deleted so that's why I added status 0
    all_routes = AllRoutes.query.filter_by(route_id=route_id).first()
    all_routes.status = 0
    db.session.commit()
    print(all_routes.status, all_routes.route_id)
    print("------------in delete fn\n", routes_stop[new_var])

    return render_template('views/edit_route.html', response=response, points=points, route_name=route_name,
                           route_id=route_id, stops_dict=stops_dict, points_len=len(points))

 
@app.route('/add/<route_id>/', methods=['POST', 'GET'])
@login_required
def add(route_id):  # add stop in list not in stops.txt
    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)

    global routes_stop

    db_response = db.session.query(AllRoutes).filter_by(route_id=route_id, user_id=user.id).first()
    route_name = db_response.route_name

    new_var = str(user.id) + "_" + str(route_id)

    new_list = routes_stop[new_var]

    if len(new_list) == 0:
        routes_stop[new_var] = literal_eval(db_response.stop_details)
        new_list = routes_stop[new_var]
    # fetch stop details

    if request.method == 'POST':
        stops_data = stops.query.filter_by(user_id=current_user.id).all()
        stops_df = pd.DataFrame([(stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon) for stop in stops_data],
                                columns=['stop_id', 'stop_name', 'stop_lat', 'stop_lon'])
        # stops_df = pd.read_csv(f'data/{user.username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip})
        k = [str(i[0]) for i in new_list]
        route_stops_df = stops_df.set_index('stop_id').loc[k].reset_index(inplace=False)[
            ['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]
        list1 = np.array(route_stops_df.values.tolist())

        temp_list = []
        print('request.form[lat1]', request.form['lat1'])
        lat = float(request.form['lat1'])

        long = float(request.form['long1'])
        stop_names = request.form['stop_name1']
        stop_ids = request.form['stop_id1']
        fare_stage = 0
        temp_list.append(stop_ids)
        temp_list.append(fare_stage)

        print('new stop', temp_list)
        new_list.append(temp_list)
        routes_stop[new_var] = new_list
        # new_list  = np.array(new_list)
        print('new list\n', new_list)

        temp_list2 = []
        temp_list2.append(stop_ids)

        temp_list2.append(stop_names)
        temp_list2.append(lat)
        temp_list2.append(long)
        # np.array(temp_list)
        print('temp list', temp_list2)
        print("----list1 in new route", len(list1), type(list1))

        if len(list1) == 0:
            list1 = np.array([temp_list2])
        else:
            list1 = np.vstack([list1, temp_list2])
        # list1 = np.append(list1,temp_list,axis=0)

        print("\nafter append\n", list1)

        # print("new list in new route",new_list)
        modified_list = list1
        #     print("-------modified _list\n",modified_list)
        points = modified_list[:, [2, 3]].astype(float).tolist()

        for i in range(len(modified_list)):
            points[i].insert(0, modified_list[i][0])

        points_len = len(points)
        response = modified_list[:, 0:5].tolist()
        # stops_df = pd.read_csv(f'data/{user.username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip})
        # print(stops_df.set_index('stop_id').T.to_dict('list'))
        # stops_dict = dict([(i,[i,a,b,c ]) for i, a,b,c in zip(stops_df.stop_id, stops_df.stop_name,stops_df.stop_lat,stops_df.stop_lon)]) #dict to fetch all the stop details
        stops_dict = {stop.stop_id: [stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon] for stop in stops_data}
        print("list after add----- \n", routes_stop[new_var])
        # in route stop deleted so that's why I added status 0
        all_routes = AllRoutes.query.filter_by(route_id=route_id).first()
        all_routes.status = 0
        db.session.commit()
        return render_template('views/edit_route.html', response=response, points=points, route_name=route_name,
                               route_id=route_id, stops_dict=stops_dict, points_len=points_len)


# call this function after drag and
@app.route("/updateList/<route_id>", methods=["POST", "GET"])
@login_required
def updateList(route_id):
    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)
    db_response = db.session.query(AllRoutes).filter_by(route_id=route_id, user_id=user.id).first()
    route_name = db_response.route_name

    new_var = str(user.id) + "_" + str(route_id)

    global routes_stop

    print("in update")
    if request.method == 'POST':
        print("post hit")
        new_list = routes_stop[new_var]
        getorder = request.json['data']
        print("\t-----getorder----\n", getorder)

        # getorder = "["+getorder+"]"
        r = getorder.split(",")

        # r=literal_eval(str(getorder))
        # r is temporary list to store the modified order we get from ajax
        # print("\t----------order---\n",r)

        # r = [str(x) for x in r]
        print("\t----------modified get order---\n", r)

        #    #call previous listorder from data
        if len(new_list) == 0:
            routes_stop[new_var] = literal_eval(db_response.stop_details)  # fetch stop details
            print('line 544', route_name)
            new_list = routes_stop[new_var]

        # print("\t-----before ordering global new list-----\n",new_list)
        t = []
        list1 = []  # temporary list to store order of stops we get from ajax
        for i in new_list:
            list1.append(i[0])
        print("=====new list order previous==== \n", list1)
        for i in new_list:
            t.append(r.index(i[0]))

        print('---------------t----------\n', t)
        print()
        # for x,y in sorted(zip(t,new_list)):
        #     print(x,y)
        # set previous stops order according to received ordered from ajax
        new_list = [y for x, y in sorted(zip(t, new_list))]
        stops_data = stops.query.filter_by(user_id=current_user.id).all()
        stops_df = pd.DataFrame([(stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon) for stop in stops_data],
                                columns=['stop_id', 'stop_name', 'stop_lat', 'stop_lon'])
        # stops_df = pd.read_csv(f'data/{user.username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip})
        print("modified list", new_list)
        routes_stop[new_var] = new_list

        k = [str(i[0]) for i in new_list]
        route_stops_df = stops_df.set_index('stop_id').loc[k].reset_index(inplace=False)[
            ['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]
        modified_list = np.array(route_stops_df.values.tolist())

        # points = modified_list[:, [0, 2, 3]].astype(float).tolist()
        points = modified_list[:, [2, 3]].astype(float).tolist()

        for i in range(len(modified_list)):
            points[i].insert(0, modified_list[i][0])

        points_len = len(points)
        response = modified_list[:, 0:5].tolist()
        # in route stop deleted so that's why I added status 0
        all_routes = AllRoutes.query.filter_by(route_id=route_id).first()
        all_routes.status = 0
        db.session.commit()
        return jsonify({'route_name': route_name, 'route_id': route_id, 'points': points, 'response': response,
                        'points_len': points_len})


@app.route('/new_add/<route_id>/', methods=['POST', 'GET'])  # this is call to add new stop in csv
@login_required
def new_add(route_id):
    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)

    db_response = db.session.query(AllRoutes).filter_by(route_id=route_id, user_id=user.id).first()
    route_name = db_response.route_name

    new_var = str(user.id) + "_" + str(route_id)

    global routes_stop

    print("in new add")
    # stops_df = pd.read_csv('data/gtfs/stops.txt', dtype={"stop_id": str})
    # print(stops_df.set_index('stop_id').T.to_dict('list'))
    # k = dict([(i,[i,a,b,c ]) for i, a,b,c in zip(stops_df.stop_id, stops_df.stop_name,stops_df.stop_lat,stops_df.stop_lon)]) #dict to fetch all the stop details
    # new_list = routes_stop[new_var]
    new_list = routes_stop.get(new_var, [])
    stops_data = stops.query.filter_by(user_id=current_user.id).all()
    stops_df = pd.DataFrame([(stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon) for stop in stops_data],
                            columns=['stop_id', 'stop_name', 'stop_lat', 'stop_lon'])
    # stops_df = pd.read_csv(f'data/{user.username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip}) #stop_code,stop_id,stop_lat,stop_lon,stop_name,wheelchair_boarding,zone_id
    if request.method == 'POST':

        # print("--------------\n",new_list)
        if len(new_list) == 0:
            routes_stop[new_var] = literal_eval(db_response.stop_details)  # fetch stop details
            new_list = routes_stop[new_var]

        k = [str(i[0]) for i in new_list]

        print("----k--\n", k)
        route_stops_df = stops_df.set_index('stop_id').loc[k].reset_index(inplace=False)[
            ['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]
        list1 = np.array(route_stops_df.values.tolist())

        stop_id_option = request.form['set_stop_id']
        new_stop_id = request.form['new_stop_id']
        stop_names = request.form['stop_name']
        lat = float(request.form['lat'])
        long = float(request.form['long'])

        k = []  # temporary list

        stop_ids = None  # by default

        if stop_id_option == 'default_id':

            stop_ids = generate_hexcode(lat, long, stop_names)

            flash("Stop has been added!")
        else:
            stop_id_exists = db.session.query(exists().where(stops.stop_id == new_stop_id)).scalar()

            if stop_id_exists:
                # Show an alert message that the stop_id already exists
                flash('Stop ID already exists. Please enter a different stop ID.')
            else:
                stop_ids = new_stop_id

        k.append(str(stop_ids))
        k.append(0)
        print('----k---', k)
        new_list.append(k)

        routes_stop[new_var] = new_list
        # new_list  = np.array(new_list)
        print("---new list", routes_stop[new_var])

        k2 = []
        k2.append(str(stop_ids))

        k2.append(stop_names)
        k2.append(lat)
        k2.append(long)

        if len(list1) == 0:
            list1 = np.array([k2])




        else:
            list1 = np.vstack([list1, k2])

        if request.form['new_stop_id'] == 'empty':
            data = [{'stop_id': int(k[0]), 'stop_name': k2[1], 'stop_lat': k2[2], 'stop_lon': k2[3]}]
        else:
            data = [{'stop_id': k[0], 'stop_name': k2[1], 'stop_lat': k2[2], 'stop_lon': k2[3]}]

        # stops_df = stops_df.append(data,ignore_index=False,sort=False)

        # stops_df.to_csv(f'data/{user.username}/new_stops.txt',index=False)

        stops_data = [stops(stop_id=item['stop_id'], stop_name=item['stop_name'], stop_lat=item['stop_lat'],
                            stop_lon=item['stop_lon'], user_id=current_user.id) for item in data]
        db.session.add_all(stops_data)
        db.session.commit()

        # print("----addedd stop detais---\n",k)
        # print("-----\nprevious details---\n",new_list[1]) # ['2388', 'Jaitpur Crossing', 28.496767, 77.302417]
        # list1 = [] # temporary list to store order of stops we get from ajax
        # for i in new_list:
        #     list1.append(i[0])
        print("=========list after adding new element===\n", list1)
        modified_list = list1
        # points = modified_list[:, [0, 2, 3]].astype(float).tolist()
        points = modified_list[:, [2, 3]].astype(float).tolist()

        for i in range(len(modified_list)):
            points[i].insert(0, modified_list[i][0])

        points_len = len(points)
        response = modified_list[:, 0:5].tolist()
        # stops_df = pd.read_csv(f'data/{user.username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip})
        stops_data = stops.query.filter_by(user_id=current_user.id).all()
        # stops_df = pd.DataFrame([(stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon) for stop in stops_data], columns=['stop_id', 'stop_name', 'stop_lat', 'stop_lon'])
        # stops_dict = dict([(i,[i,a,b,c ]) for i, a,b,c in zip(stops_df.stop_id, stops_df.stop_name,stops_df.stop_lat,stops_df.stop_lon)]) #dict to fetch all the stop details
        stops_dict = {stop.stop_id: [stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon] for stop in stops_data}
        all_routes = AllRoutes.query.filter_by(route_id=route_id).first()
        all_routes.status = 0
        db.session.commit()
        return render_template('views/edit_route.html', response=response, points=points, route_name=route_name,
                               route_id=route_id, stops_dict=stops_dict, points_len=points_len)


@app.route("/save_route/<route_id>", methods=['POST', 'GET'])
@login_required
def save_route(route_id):
    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)
    print("in save route")

    new_var = str(user.id) + "_" + str(route_id)

    global all_stops_deleted
    db_response = db.session.query(AllRoutes).filter_by(route_id=route_id, user_id=user.id).first()
    global routes_stop

    new_list = routes_stop[new_var]
    route_name = db_response.route_name

    if request.method == 'POST':

        getorder = request.json['data']
        for key, val in getorder.items():
            getorder[key] = '1' if val else "0"

        if len(new_list) != 0:
            for i, x in enumerate(new_list):
                if x[0] in getorder:
                    x[4] = getorder[x[0]]
                    print("line n0 442\n", x)
            else:
                print("line n0 444\n", x)

            db_response.stop_details = str(new_list)

            db.session.commit()
        else:
            if all_stops_deleted == True:
                db_response.stop_details = str(new_list)

                db.session.commit()
            else:
                new_list = literal_eval(db_response.stop_details)
                for i, x in enumerate(new_list):
                    if x[0] in getorder:
                        x[4] = getorder[x[0]]
                        print("line n0 460\n", x)
                    else:
                        print("line n0 462\n", x)

                db_response.stop_details = str(new_list)
                db.session.commit()

        all_routes = AllRoutes.query.filter_by(route_id=route_id).first()
        print(all_routes.status)
        if all_routes.status == 0:
            trip_ids = trips.query.filter_by(route_id=route_id, user_id=current_user.id).all()
            trip_id_list = [trip.trip_id for trip in trip_ids]
            trip_freq = [trip.service_id for trip in trip_ids]
            trip_speed = [trip.speed for trip in trip_ids]

            # Delete each trip ID
            for trip in trip_ids:
                db.session.delete(trip)

            print(trip_id_list)
            print(trip_freq)
            print(trip_speed)

            recreate_trips(trip_id_list, trip_freq, trip_speed, route_id)

            print("Trip has been Updated!")

            all_routes.status = 1

            db.session.commit()

    print("\n\n---save in database------\n\n")
    folium_map, response, route_name = plot(route_id, user.id, user.username)

    return render_template('views/view.html', map=folium_map, response=response, route_name=route_name,
                           route_id=route_id)


# function to create route------------------

def convertToNumber(s):
    return int.from_bytes(s.encode(), 'little')


def route_generate_hexcode(user_id, route_name):
    input_string = bytes(f"{user_id}{route_name}".lower(), encoding='utf-8')
    hash_object = hashlib.sha256(input_string)
    hex_dig = hash_object.hexdigest()[:8].upper()
    return hex_dig


@app.route("/create/", methods=['POST', 'GET'])
@login_required
def create():
    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)
    #    agency_id,route_id,route_long_name,route_short_name,route_type
    print("in the create function", user.id)
    # route_name='2196UP'

    if request.method == 'POST':

        print("---create route with name--", request.form['rt_name'])
        rt_name = request.form['rt_name']
        rt_option = request.form['select_rdbt']
        new_rt_id = request.form['rt_id']
        copy_route_id = request.form.get("copyRoute")

        existed_rt_name = AllRoutes.query.filter_by(route_name=rt_name, user_id=user.id).first()

        if existed_rt_name is not None:
            flash('Route with same name exist, choose another route name !!')
            return redirect(url_for('index'))

        status = 1
        stop_details = '[]'

        obj_agency = AllRoutes.query.filter_by(user_id=user.id).first()

        # obj = db.session.query(AllRoutes).order_by(AllRoutes.id.desc()).first()

        if rt_option == 'rdbt1':

            route_id = route_generate_hexcode(str(user.id), rt_name)
            existed_rt_id = AllRoutes.query.filter_by(route_id=str(route_id), user_id=user.id).first()

            while (existed_rt_id is not None):
                route_id = route_id[::-1]
                existed_rt_id = AllRoutes.query.filter_by(route_id=str(route_id), user_id=user.id).first()
        else:
            route_id = new_rt_id
            existed_rt_id = AllRoutes.query.filter_by(route_id=str(route_id), user_id=user.id).first()

            if existed_rt_id is not None:
                flash('Enter Unique Route ID')
                return redirect(url_for('index'))

        print("--------route id of new route name--- : ", route_id)

        # # route_id = int(obj.route_id)+1
        user_id = user.id
        if obj_agency is None:
            agency_id = user.agency
        else:
            agency_id = obj_agency.agency_id
        if copy_route_id != "":
            copy_route_details = AllRoutes.query.filter_by(route_id=str(copy_route_id), user_id=user.id).first()
            stop_details = copy_route_details.stop_details

        all_routes_obj = AllRoutes(route_id, rt_name, agency_id, status, stop_details, user_id)
        route_ind = routes(agency_id=agency_id, route_id=route_id, route_long_name=rt_name, route_short_name=rt_name,
                           route_type=status, user_id=user_id)
        db.session.add(all_routes_obj)
        db.session.add(route_ind)
        db.session.commit()
        print("object created", all_routes_obj.route_id)
        flash("Route has been created !")

        return redirect(url_for('index'))


# @app.route("/delete-route/route_id")
# def delete_route():
# User.query.filter_by(id=123).delete()

@app.route("/delete_route/<string:rt_name>")
@login_required
def delete_route(rt_name):
    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)
    print('in delete', rt_name)
    delete_rt_name = AllRoutes.query.filter_by(route_id=rt_name, user_id=user.id).first()
    if delete_rt_name is None:
        flash("Route not exist")
        return redirect(url_for('index'))

    # z=db.session.query(AllRoutes).filter_by(route_name=rt_name,user_id=user.id)
    print("in delte functiom ", delete_rt_name)
    # db.session.query(AllRoutes).filter_by(route_name=rt_name,user_id=user.id).delete()
    db.session.delete(delete_rt_name)
    db.session.commit()
    print('-----------------deleted-----  ')
    print()
    return redirect(url_for('index'))


@app.route("/find_buses_within_radius/", methods=["POST", "GET"])
@login_required
def find_buses_within_radius():
    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)

    print("in bus location\n")
    # print(lat,long)
    radius = 1
    # radius in kilometers
    if request.method == 'POST':
        print("post hit")
        print(request.json['data'])

        getorders = literal_eval(request.json['data'])
        print(type(getorders[0]))
        q_lat = getorders[0]
        q_lng = getorders[1]

        stops_data = stops.query.filter_by(user_id=user.id).all()
        vehicle_lats = [float(stop.stop_lat) for stop in stops_data]
        vehicle_lngs = [float(stop.stop_lon) for stop in stops_data]

        # df = pd.read_csv(f'data/{user.username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip}) #stop_code,stop_id,stop_lat,stop_lon,stop_name,wheelchair_boarding,zone_id
        # vehicle_lats = df['stop_lat'].values.astype(float)
        # vehicle_lngs = df['stop_lon'].values.astype(float)

        stst = 6367 * 2 * np.arcsin(np.sqrt(
            np.sin((np.radians(vehicle_lats) - math.radians(q_lat)) / 2) ** 2 + math.cos(
                math.radians(q_lat)) * np.cos(np.radians(vehicle_lats)) * np.sin(
                (np.radians(vehicle_lngs) - math.radians(q_lng)) / 2) ** 2))
        bus_record_indices_within_radius = np.where(stst <= radius)[0]

        z = []
        for index in bus_record_indices_within_radius:
            stop = stops_data[index]
            z.append([stop.stop_id, stop.stop_lat, stop.stop_lon, stop.stop_name])
        # z = df.iloc[bus_record_indices_within_radius][['stop_id','stop_lat','stop_lon','stop_name']].values

        z = np.array(z)

        coord_response = z[:, 0:5].tolist()
        coord_points = z[:, [1, 2]].astype(float).tolist()
        # coord_response = z
        # coord_points = [[float(row[1]), float(row[2])] for row in z]
        print(coord_response)
        # for i in z:
        #     print("*",i)

        return jsonify({'coord_response': coord_response, 'coord_points': coord_points})


@app.route('/change_location/<route_id>/', methods=['POST', 'GET'])  # this is call to add new stop in csv
@login_required
def change_location(route_id):
    print("in experiment fn")

    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)

    new_var = str(user.id) + "_" + str(route_id)
    global routes_stop

    db_response = db.session.query(AllRoutes).filter_by(route_id=route_id, user_id=user.id).first()
    new_list = routes_stop[new_var]
    route_name = db_response.route_name

    print("in experiment fn")
    # stop_id = '9991'
    if len(new_list) == 0:
        routes_stop[new_var] = literal_eval(db_response.stop_details)
        new_list = routes_stop[new_var]  # fetch stop details

    stops_data = stops.query.filter_by(user_id=current_user.id).all()
    stops_df = pd.DataFrame([(stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon) for stop in stops_data],
                            columns=['stop_id', 'stop_name', 'stop_lat', 'stop_lon'])
    # stops_df = pd.read_csv(f'data/{user.username}/new_stops.txt', dtype={"stop_id": str,"stop_name":str},converters={"stop_id": str.strip,"stop_name":str.strip})
    if request.method == "POST":
        lat = float(request.form['lat2'])

        long = float(request.form['long2'])
        stop_ids = request.form['stop_id2']

        print(lat, long, stop_ids)

    # stops_df.loc[stops_df["stop_id"]== stop_ids,"stop_lat"]= lat
    # stops_df.loc[stops_df["stop_id"]== stop_ids,"stop_lon"]= long
    # stops_df.to_csv(f'data/{user.username}/new_stops.txt',index=False)

    stop = stops.query.filter_by(user_id=current_user.id, stop_id=stop_ids).first()

    if stop:
        stop.stop_lat = lat
        stop.stop_lon = long
        db.session.commit()

    stops_data = stops.query.filter_by(user_id=current_user.id).all()
    stops_df = pd.DataFrame([(stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon) for stop in stops_data],
                            columns=['stop_id', 'stop_name', 'stop_lat', 'stop_lon'])

    k = [str(i[0]) for i in new_list]
    route_stops_df = stops_df.set_index('stop_id').loc[k].reset_index(inplace=False)[
        ['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]
    list1 = np.array(route_stops_df.values.tolist())

    modified_list = list1
    # points = modified_list[:, [0, 2, 3]].astype(float).tolist()
    points = modified_list[:, [2, 3]].astype(float).tolist()

    for i in range(len(modified_list)):
        points[i].insert(0, modified_list[i][0])

    points_len = len(points)
    response = modified_list[:, 0:5].tolist()
    # stops_dict = dict([(i,[i,a,b,c ]) for i, a,b,c in zip(stops_df.stop_id, stops_df.stop_name,stops_df.stop_lat,stops_df.stop_lon)]) #dict to fetch all the stop details
    stops_dict = {stop.stop_id: [stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon] for stop in stops_data}
    return render_template('views/edit_route.html', response=response, points=points, route_name=route_name,
                           route_id=route_id, stops_dict=stops_dict, points_len=points_len)


# --for export gtfs-----------------------------


@app.route("/download_gtfs/", methods=['POST', 'GET'])
@login_required
def download_gtfs():
    user = User.query.filter_by(id=current_user.id).first()
    login_user(user)
    print("\n----in export function----")

    # Call the function to create GTFS files and get the file path
    file_path = create_gtfs_files(current_user.id, current_user.username, current_user.agency)

    directory_path = f"data/{current_user.agency}/{current_user.username}/Exported_files"

    filenames = ['routes.txt', 'stops.txt', 'trips.txt', 'stop_times.txt']
    delete_files(directory_path, filenames)

    if os.path.exists(file_path):
        print("Yes exported file here")
        return send_file(file_path, as_attachment=True)

    flash("Data has been exported!")
    return redirect(url_for('index'))


def convert_to_gtfs(data_list, filename):
    # Define the file path
    file_path = f'data/{current_user.agency}/{current_user.username}/Exported_files/{filename}.txt'

    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Write the data to a CSV file
    with open(file_path, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=data_list[0].keys())
        writer.writeheader()
        writer.writerows(data_list)


def create_gtfs_files(user_id, username, agency):
    # Retrieve data from the respective database tables
    routes_data = routes.query.filter_by(user_id=user_id).all()
    trips_data = trips.query.filter_by(user_id=user_id).all()
    stops_data = stops.query.filter_by(user_id=user_id).all()
    stop_times_data = stopTimes.query.filter_by(user_id=user_id).all()

    # Extract the relevant data from the objects into lists
    routes_list = [{'agency_id': route.agency_id, 'route_id': route.route_id, 'route_long_name': route.route_long_name,
                    'route_short_name': route.route_short_name, 'route_type': route.route_type} for route in
                   routes_data]
    trips_list = [
        {'route_id': trip.route_id, 'service_id': trip.service_id, 'trip_id': trip.trip_id, 'speed': trip.speed,
         'shape_id': trip.shape_id, 'freq': trip.freq} for trip in trips_data]
    stops_list = [
        {'stop_id': stop.stop_id, 'stop_code': stop.stop_code, 'stop_name': stop.stop_name, 'stop_lat': stop.stop_lat,
         'stop_lon': stop.stop_lon, 'zone_id': stop.zone_id} for stop in stops_data]
    stop_times_list = [{'trip_id': stopTimes.trip_id, 'arrival_time': stopTimes.arrival_time,
                        'departure_time': stopTimes.departure_time, 'stop_id': stopTimes.stop_id,
                        'stop_sequence': stopTimes.stop_sequence} for stopTimes in stop_times_data]

    # Convert the data to GTFS files
    convert_to_gtfs(routes_list, 'routes')
    convert_to_gtfs(trips_list, 'trips')
    convert_to_gtfs(stops_list, 'stops')
    convert_to_gtfs(stop_times_list, 'stop_times')

    # Get the current timestamp
    timestamp = datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')

    # Create the GTFS zip file with the timestamp
    directory_path = f'data/{agency}/{username}/Exported_files'
    zip_file_path = os.path.join(directory_path, f'{agency}_gtfs_{timestamp}.zip')
    with zipfile.ZipFile(zip_file_path, 'w') as zip_out:
        for file_name in os.listdir(directory_path):
            if file_name.endswith('.txt'):
                file_path = os.path.join(directory_path, file_name)
                zip_out.write(file_path, os.path.basename(file_path))

    # Return the file path
    return zip_file_path


def delete_files(directory_path, filenames):
    for filename in filenames:
        file_path = os.path.join(directory_path, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"File {file_path} deleted successfully.")
        else:
            print(f"File {file_path} does not exist.")


# @app.route("/download/",methods = ['POST', 'GET'])
# @login_required
# def download():
#     user = User.query.filter_by(id=current_user.id).first()
#     login_user(user)

#     # stops_route(user.username)
#     file_name = f"{user.username}_export_all.zip"

#     if os.path.exists(file_name):
#             return send_file(file_name,as_attachment=True)

#     flash('Please Export Gtfs First')
#     return redirect(url_for('index'))

# # file_name = "db.sqlite3"

@app.route("/delete_gtfs", methods=['POST', 'GET'])
def delete_gtfs():
    # Clear all tables except User
    db.session.query(trips).delete()
    db.session.query(stops).delete()
    db.session.query(stopTimes).delete()
    db.session.query(routes).delete()
    db.session.query(AllRoutes).delete()
    db.session.commit()

    flash('DB has been deleted!')
    return redirect(url_for('index'))


@app.route("/download_db", methods=['POST', 'GET'])
def download_db():
    # stops_route(user.username)
    file_name = "db.sqlite3"

    if os.path.exists(file_name):
        return send_file(file_name, as_attachment=True)

    flash('file not exists')
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'GET':
        return redirect(url_for('adminMain'))
    users = User.query.all()
    all_users = {}
    index = 1;
    for i in users:
        all_users[index] = i.username
        index += 1
        print(all_users)
    return render_template('views/admin.html', all_users=all_users)


# def allowed_file(filename):
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploader', methods=['GET', 'POST'])
def uploader():
    if request.method == 'POST':
        flash('Files uploaded successfully')
        file1 = request.files['file1']
        username = current_user.username

        print(username, "   ", file1)

        # Define the directory path
        agency = current_user.agency  # Replace with your agency name
        user_username = secure_filename(username)
        directory_path = f'data/{agency}/{user_username}/Imported_files'

        # Create the directory if it doesn't exist
        os.makedirs(directory_path, exist_ok=True)

        timestamp = datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
        zip_file_path = os.path.join(directory_path, f'{current_user.agency}_gtfs_{timestamp}.zip')

        with ZipFile(file1, 'r') as zip:
            print("*")
            for file_name in zip.namelist():
                if file_name.endswith('.txt'):
                    file_path = os.path.join(directory_path, os.path.basename(file_name))
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, 'wb') as f:
                        f.write(zip.read(file_name))

            print('Done!')

        with zipfile.ZipFile(zip_file_path, 'w') as zip_out:
            with zipfile.ZipFile(file1, 'r') as zip_in:
                for file_name in zip_in.namelist():
                    if file_name.endswith('.txt'):
                        file_data = zip_in.read(file_name)
                        zip_out.writestr(os.path.basename(file_name), file_data)

        make_all_routes(username, agency)

        directory_path = f"data/{current_user.agency}/{current_user.username}/Imported_files"

        filenames = ['routes.txt', 'stops.txt', 'trips.txt', 'stop_times.txt']
        delete_files(directory_path, filenames)

        flash("Data has been updated!!")

        return redirect(url_for('index'))

    flash('Files not uploaded')

    return redirect(url_for('index'))

@socketio.on('connect')
def test_connect():
    emit('connection_response', {'data': 'Connected'})

if __name__ == '__main__':
    socketio.run(app)
    app.debug = True
    app.run(port=8080)
