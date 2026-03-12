"""Exception hierarchy for scraping operations."""


class ScrapingError(Exception):
    """Base exception for all scraping-related errors."""

    def __init__(self, message: str, url: str | None = None) -> None:
        """Initialize scraping error.

        Args:
            message: Error description.
            url: URL where error occurred.
        """
        self.url = url
        super().__init__(message)


class TimeoutError(ScrapingError):
    """Raised when page load or element wait times out."""

    def __init__(
        self, message: str, url: str | None = None, timeout_ms: int | None = None
    ) -> None:
        """Initialize timeout error.

        Args:
            message: Error description.
            url: URL where timeout occurred.
            timeout_ms: Timeout duration in milliseconds.
        """
        self.timeout_ms = timeout_ms
        super().__init__(message, url)


class SelectorNotFoundError(ScrapingError):
    """Raised when a CSS/XPath selector matches no elements."""

    def __init__(
        self, message: str, url: str | None = None, selector: str | None = None
    ) -> None:
        """Initialize selector not found error.

        Args:
            message: Error description.
            url: URL where selector failed.
            selector: The selector that was not found.
        """
        self.selector = selector
        super().__init__(message, url)


class RateExtractionError(ScrapingError):
    """Raised when rate cannot be extracted from page content."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        raw_text: str | None = None,
    ) -> None:
        """Initialize rate extraction error.

        Args:
            message: Error description.
            url: URL where extraction failed.
            raw_text: The raw text that couldn't be parsed.
        """
        self.raw_text = raw_text
        super().__init__(message, url)


class ParseError(ScrapingError):
    """Raised when page content cannot be parsed."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        content_type: str | None = None,
    ) -> None:
        """Initialize parse error.

        Args:
            message: Error description.
            url: URL where parsing failed.
            content_type: Type of content that couldn't be parsed.
        """
        self.content_type = content_type
        super().__init__(message, url)
