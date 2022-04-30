from app import celery, app
from zipfile import ZipFile
import os


@celery.task()
def verify_uploaded_defence(filename):
    with ZipFile(
        os.path.join(app.config["TEMPORARY_UPLOAD_FOLDER"], filename), mode="r"
    ) as zip:
        print(zip.filename)
