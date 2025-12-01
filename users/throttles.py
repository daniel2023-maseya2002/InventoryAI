# users/throttles.py
from rest_framework.throttling import SimpleRateThrottle

class RequestCodeThrottle(SimpleRateThrottle):
    scope = "request_code"

    def get_cache_key(self, request, view):
        # throttle by IP + email (if provided)
        ident = self.get_ident(request)
        email = None
        try:
            email = request.data.get("email", "").lower().strip()
        except Exception:
            email = ""
        # if email provided throttle by email
        if email:
            return f"throttle_request_code_{email}"
        # fallback to IP
        return f"throttle_request_code_ip_{ident}"
