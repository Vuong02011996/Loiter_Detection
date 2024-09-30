from flask import Flask, Blueprint
from flask_restx import Api
from flask_cors import CORS
import os
from dotenv import load_dotenv
import sys
import multiprocessing as mp
from app.services.loiter_detection.loitering_detection_services_with_oryza_AI_v1 import blueprint as loiter_namespace
# from app.services.cross_line_detection.cross_line_detection_services_with_oryza_AI_v1 import blueprint as cross_line_namespace
from pathlib import Path  # Python 3.6+ only
import sentry_sdk
import logging

sentry_sdk.init("https://2f59b679dd6049b7bcb9bba1a45276ee@sentry.oryza.vn/4")
sentry_sdk.capture_message(f"[LOITERING][192.168.103.81] START SERVICE")
# reduce log level
# https://github.com/pika/pika/issues/692
logging.getLogger("pika").setLevel(logging.WARNING)
# or, disable propagation
logging.getLogger("pika").propagate = False


if len(sys.argv) > 1:
    print("The script run with file {}".format(sys.argv[1]))
    env_path = Path(".") / sys.argv[1]
    print("env_path", env_path)
    load_dotenv(dotenv_path=env_path)
else:
    print("The script run with file .env")
    env_path = Path(".") / ".env"
    load_dotenv(dotenv_path=env_path)

# load_dotenv()

app = Flask(__name__)

CORS(app)
# Using both register_blueprint and namespace
api_blueprint = Blueprint('api', __name__, url_prefix='/api')
api = Api(api_blueprint, title="Loitering Detection Project", version="1.0.0", description="Swagger API Homepage")

# Using api for oryza AI from root
app.register_blueprint(loiter_namespace)
# app.register_blueprint(cross_line_namespace)
app.register_blueprint(api_blueprint)

if __name__ == "__main__":
    mp.set_start_method('spawn')
    app.run(host=os.getenv("SERVER_HOST"), port=os.getenv("SERVER_PORT_LOITERING"), threaded=True, debug=True, use_reloader=False)

    """
    Run pm2 auto start when reboot 
    pm2 start ecosystem.staging.config.yaml
    pm2 startup - copy command and run 
    pm2 save 
    """
    """
    run staging -> have data => not error in code
    run video product -> have data => model in product not error
    run product 
    """

