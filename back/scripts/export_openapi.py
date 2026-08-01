import json
import sys

from app.main import create_app


json.dump(create_app().openapi(), sys.stdout, ensure_ascii=False)
sys.stdout.write('\n')
