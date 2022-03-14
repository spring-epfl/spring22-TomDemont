# spring22-TomDemont
Repository for Tom Demont semester project: Privacy Competition Platform for [SecretStroll](https://github.com/spring-epfl/CS-523-public/tree/master/secretstroll) project in CS-523.

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

## Credits
The Flask app is created following the useful and very detailed guides from [Miguel Grinberg](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world).