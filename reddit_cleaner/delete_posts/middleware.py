from django.conf import settings


class SecurityHeadersMiddleware:
    """Adds a CSP and a few headers Django's SecurityMiddleware does not."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", settings.CONTENT_SECURITY_POLICY)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("Cache-Control", "no-store")
        return response
