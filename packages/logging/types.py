# Logging types
from enum import StrEnum


class LogEvent(StrEnum):
    APPLICATION_STARTED = "application_started"
    APPLICATION_STOPPED = "application_stopped"

    HTTP_REQUEST = "http_request"
    HTTP_RESPONSE = "http_response"

    DATABASE_QUERY = "database_query"

    REDIS_COMMAND = "redis_command"

    AI_REQUEST = "ai_request"
    AI_RESPONSE = "ai_response"

    FILE_UPLOAD = "file_upload"

    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"

    ERROR = "error"