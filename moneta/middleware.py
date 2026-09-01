from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Middleware that attaches Content-Security-Policy and Permissions-Policy
    headers to HTTP responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Content-Security-Policy
        csp_policy = getattr(settings, 'CONTENT_SECURITY_POLICY', None)
        if csp_policy and 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = csp_policy

        # Permissions-Policy
        permissions_policy = getattr(settings, 'PERMISSIONS_POLICY', None)
        if permissions_policy and 'Permissions-Policy' not in response:
            response['Permissions-Policy'] = permissions_policy

        return response

