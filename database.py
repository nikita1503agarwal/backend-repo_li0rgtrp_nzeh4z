"""
Database Helper Functions

MongoDB helper functions ready to use in your backend code.
Import and use these functions in your API endpoints for database operations.
"""

from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from typing import Union, Optional, List, Dict, Any
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

_client = None
db = None

database_url = os.getenv("DATABASE_URL")
database_name = os.getenv("DATABASE_NAME")

if database_url and database_name:
    _client = MongoClient(database_url)
    db = _client[database_name]

# ------------- Utilities -------------

def to_object_id(id_str: str) -> ObjectId:
    return ObjectId(id_str)

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])  # type: ignore
    return doc

# Helper functions for common database operations

def create_document(collection_name: str, data: Union[BaseModel, dict]):
    """Insert a single document with timestamp"""
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")

    # Convert Pydantic model to dict if needed
    if isinstance(data, BaseModel):
        data_dict = data.model_dump()
    else:
        data_dict = data.copy()

    data_dict['created_at'] = datetime.now(timezone.utc)
    data_dict['updated_at'] = datetime.now(timezone.utc)

    result = db[collection_name].insert_one(data_dict)
    return str(result.inserted_id)


def get_documents(collection_name: str, filter_dict: dict = None, limit: Optional[int] = None, sort: Optional[List[tuple]] = None):
    """Get documents from collection"""
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")
    cursor = db[collection_name].find(filter_dict or {})
    if sort:
        cursor = cursor.sort(sort)
    if limit:
        cursor = cursor.limit(limit)
    return [serialize_doc(d) for d in list(cursor)]


def get_document_by_id(collection_name: str, id_str: str):
    if db is None:
        raise Exception("Database not available.")
    doc = db[collection_name].find_one({"_id": to_object_id(id_str)})
    return serialize_doc(doc) if doc else None


def update_document(collection_name: str, id_str: str, update_data: dict):
    if db is None:
        raise Exception("Database not available.")
    update_data['updated_at'] = datetime.now(timezone.utc)
    result = db[collection_name].update_one({"_id": to_object_id(id_str)}, {"$set": update_data})
    return result.modified_count > 0


def delete_document(collection_name: str, id_str: str):
    if db is None:
        raise Exception("Database not available.")
    result = db[collection_name].delete_one({"_id": to_object_id(id_str)})
    return result.deleted_count > 0
