class SDKException(Exception):
    """Base SDK exception."""


class BadRequestException(SDKException):
    pass


class UnauthorizedException(SDKException):
    pass


class ForbiddenException(SDKException):
    pass


class NotFoundException(SDKException):
    pass


class ConflictException(SDKException):
    pass


class RateLimitException(SDKException):
    pass


class ServerException(SDKException):
    pass