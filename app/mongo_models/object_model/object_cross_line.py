from enum import Enum
from datetime import datetime
from mongoengine import (
    StringField,
    DateTimeField,
    FloatField,
    IntField,
    BooleanField,
    LazyReferenceField,
    Document,
    LongField,
    ListField,
    EmbeddedDocumentField,
    EmbeddedDocument,
    EnumField,
    URLField,
)


class ObjectCrossLine(Document):
    process_name = StringField(required=True)
    class_name = StringField(required=True)
    branch_name = StringField(required=True)
    avatar_url_extend = StringField(required=True)
    track_id = IntField(required=True, min_value=0)
    image_person_url = StringField(required=True)
    from_frame = IntField(required=True, min_value=0)
    notified = BooleanField(default=False)
    to_frame = IntField(min_value=0)
    epoch_start = IntField(min_value=0)
    frame_start_save = IntField(min_value=0)
    save_status = StringField()
    image_url = StringField()
    box_of_track = ListField()
    # name_regions = StringField()
    # duration_time = IntField(min_value=0)

    folder_frame_track = StringField()
    clip_url = StringField()
    created_at = DateTimeField(default=datetime.utcnow, required=True)

    meta = {"collection": "objects_cross_line"}