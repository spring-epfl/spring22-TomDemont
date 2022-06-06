# spring22-TomDemont

Repository for Tom Demont semester project: Privacy Competition Platform for [SecretStroll](https://github.com/spring-epfl/CS-523-public/tree/master/secretstroll) project in CS-523.

## Introduction and purpose

In the last part of [SecretStroll](https://github.com/spring-epfl/CS-523-public/tree/master/secretstroll) project in CS-523 course, students are asked to test the limits of the sytem they built. To do so, they must simulate the execution of the software and collect the generated network trace. More information on the Secretstroll original system can be found in the [handout](https://github.com/spring-epfl/CS-523-public/blob/master/secretstroll/handout/handout_project_secretstroll.pdf) of the initial project. Here's a schematic representation of the final system: ![secretstroll-system](readme_assets/secretstroll-system.png)

In this context, students are expected to use the collected trace to extract features and create a classifier that will learn how to associate tor network trace to a grid cell id queried for in the Secretstroll application.

It is possible, in the basic shape of the application, to obtain a very efficient and accurate classifier. Students must provide a reflexion on issues and counter-measures to avoid the privacy leakage due to website fingerprinting. The current project takes place at this point: to extend Secretstroll, we aim to create a privacy competition platform where students could try different implementation and countermeasures, observe and measure the utility cost, and, afterward, attack other student's implementations to see the remaining accuracy of privacy attack machine learning based model.

This fulfills multiple pedagogical goals:

* Provide students utility measures for different implementations and see the utility/privacy tradeoff interactively
* Give students matches with train and test sets to train a model and get meaningful performance metrics for the quality of their classifier against others' implementation
* Show students a taste of an interactive and live attack-defence based study of privacy preserving mechanisms' implementation
* Give to the course team an automated tool to observe and manage student's competition

This platforms aims to gather the interactive competition aspects of [Kaggle](https://www.kaggle.com/) or [AICrowd](https://www.aicrowd.com/) platforms, while adding the inter-students match aspect to multiply the variety of network traces to attack and evaluate on both the utility and privacy metrics to observe the necessary tradeoff.

## Launch instructions

### Quick launch

```bash
git clone git@github.com:spring-epfl/spring22-TomDemont.git
cd spring22-TomDemont
```

In order to run this project, you need to have Python 3.9 installed. You are advised to create a virtual environment for this, to have a clean install of the requirements:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Finally, the next script starts (and installs in the folder if not already installed) the [Redis](https://redis.io/) message broker, starts the [Celery](https://docs.celeryq.dev/en/stable/index.html) distributed task queue and the Flask web server in development mode:

```bash
./run-srs.sh
```

After a few seconds, the server should be running on `http://localhost:5000`. All the processes can be stopped with a `Ctrl-C` SIGINT signal.

### Changing parameters

You can freely change the parameters of the application to adapt it to your needs. The modifiable environment variables are:

* `FLASK_ENV`: either development, testing or production. See [FLASK_ENV doc](https://flask.palletsprojects.com/en/2.1.x/config/#ENV)

For ease of use and avoid exporting this variable with `export FLASK_ENV=development`, this variable can be written in the `.flaskenv` file.

* `SECRET_KEY`: used to sign session cookies. See [SECRET_KEY doc](https://flask.palletsprojects.com/en/2.1.x/config/#SECRET_KEY)
* `DATABASE_URL`: the URL of the used Database. See [SQLALCHEMY_DATABASE_URI doc](https://flask-sqlalchemy.palletsprojects.com/en/2.x/config/#configuration-keys)
* `MAIL_SERVER` and `MAIL_PORT`: the server and port to use for outgoing mail support.
* `MAIL_USE_TLS`: whether the outgoing mail should be sent using STARTTLS. True if the variable is set to anything.
* `MAIL_USE_SSL`: whether the outgoing mail should be sent using SSL. True if the variable is set to anything.
* `MAIL_USERNAME` and `MAIL_PASSWORD`: credentials to use for connection to the mail server.
* `ADMIN`: the admin mail address for sending logging errors
* `MAIL_DEFAULT_SENDER`: the mail sender for mail support
* `MAIL_TEST_RECEIVER_FORMAT`: a Python format string for an email address using [plussed addressed email](https://bitwarden.com/help/generator/#username-types). Only used for development and user generation, to test receive student user email addresses.
* `MATCHES_PER_TEAM`: determines how many matches each team will be assigned at every round (should be less than the number of teams - 1)
* `MATCHES_PER_PAGE`: determines the number of matches to display on the `/index` page
* `MAX_CONTENT_LENGTH`: the maximum number of **mega** bytes any uploaded archives should not exceed.
* `UPLOAD_FOLDER` and `TEMPORARY_UPLOAD_FOLDER`: the name of the folders to save students files to (expected to already be created)
* `NB_CLASSES`: the number of possible classes the students are expected to make classification for (the number of grid cell id for Secretstroll).
* `DEFENCE_COLUMNS`: a string with the comma separated column names the uploaded network traces should have.
* `ATTACK_COLUMNS`: a string with the comma separated column names the uploaded trace classification should have. Will be appended with `proba_class_i` for `i` in `{1..NB_CASSES}` to hold the probability classification that should output the classifer.
* `CELERY_BROKER_URL` and `RESULT_BACKEND`: URLs of the message broker and result backend to use. Initially works with Redis.
* `NB_TRACES_TO_CLASSIFY`: the number of traces students should make a classification for, the size of the test set.
* `MEAN_NB_REP_PER_CLASS`: the expected mean amount of network traces to collect per grid cell id query in the Secretstroll system. Corresponds to the number of times the script `attack_defence_test_scripts/capture.sh` should be run by a student.
* `DEVIATION_NB_REP_PER_CLASS`: the accepted number of amount of traces traces per grid cell id deviating from the mean. Captures being difficult and not always perfect, students having `MEAN_NB_REP_PER_CLASS`±`DEVIATION_NB_REP_PER_CLASS` network traces for the capture on grid cell id `i` have capture accepted by the system.
* `ROWS_PER_CAPTURE`: the minimum number of rows the file holding network trace capture should have for each capture. Can be seen as the minimum number of packets we require to accept a network trace as valid.
* `LEADERBOARD_CACHE_TIME`: the number of seconds we should cache the leaderboard.

For ease of use and avoid exporting this variable with `export ADMIN="cs-523@groupes.epfl.ch"`, these variables can be written in the `.env` file, that will be loaded with the python [`dotenv`](https://pypi.org/project/python-dotenv/) module.

## User (student) guide

## User (admin) guide

## Testing

## Software architecture

### Timeline

### Data model

### Code hierarchy

<!-- ## Timeline

The software is developped following the idea of the timeline desribed in ![timeline.png](timeline.png)

## Data model

The database model can be found under `srs_model.xml` and can be visualized on the tool [https://ondras.zarovi.cz/sql/demo/](https://ondras.zarovi.cz/sql/demo/).
![model](srs_model.png)

## Run instructions

### Setup of virtual environment

Once in the cloned folder, I suggest you create a python virtual environment for this project:

```zsh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the server

Most environment variables should be set in the `.flaskenv` file. If you don't want to use it or have undeclared environment variable, export those in your environment before running e.g.:

```zsh
export FLASK_APP=srs.py
```

Then run the server with:

```zsh
flask run
```

Run Redis message broker with

```zsh
./run-redis.sh
```

Run Celery worker with

```zsh
celery -A app.celery worker --loglevel=info
``` -->

## Credits

The Flask app is created following the useful and very detailed guides from [Miguel Grinberg](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world)
