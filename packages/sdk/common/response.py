# Common response


from pydantic import BaseModel


class ApiResponse[T](BaseModel):
    success: bool
    message: str | None = None
    data: T | None = None