from datetime import datetime
from mongoengine import (
    StringField,
    DateTimeField,
    IntField,
    LazyReferenceField,
    Document,
)


class ProcessLoitering(Document):
    process_name = StringField(required=True)
    process_id = StringField(required=True)
    status_process = StringField(required=True)
    multiprocessing_pid = IntField(required=True)
    camera = LazyReferenceField("Camera")
    created_at = DateTimeField(default=datetime.utcnow, required=True)

    meta = {"collection": "process_loitering"}