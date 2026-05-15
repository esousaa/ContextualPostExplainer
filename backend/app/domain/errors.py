from http import HTTPStatus


class DomainError(Exception):
    error_code = "domain_error"
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(DomainError):
    error_code = "configuration_error"
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR


class SearchProviderRequiredError(ConfigurationError):
    error_code = "search_provider_required"
    status_code = HTTPStatus.BAD_REQUEST


class UnsupportedPlatformError(DomainError):
    error_code = "unsupported_platform"
    status_code = HTTPStatus.BAD_REQUEST


class PostNotFoundError(DomainError):
    error_code = "post_not_found"
    status_code = HTTPStatus.NOT_FOUND


class ExternalProviderError(DomainError):
    error_code = "external_provider_error"
    status_code = HTTPStatus.BAD_GATEWAY


class CitationValidationError(DomainError):
    error_code = "citation_validation_error"
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
