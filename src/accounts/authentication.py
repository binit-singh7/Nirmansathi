from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed

class QueryParamJWTAuthentication(JWTAuthentication):
    """
    Extends SimpleJWT's JWTAuthentication to also support ?token=<jwt_token>
    query parameters on requests (e.g. for direct browser PDF / certificate downloads).
    """
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                validated_token = self.get_validated_token(raw_token)
                return self.get_user(validated_token), validated_token

        # Check for token in query parameters
        raw_token = request.query_params.get('token')
        if raw_token:
            try:
                validated_token = self.get_validated_token(raw_token)
                return self.get_user(validated_token), validated_token
            except (InvalidToken, AuthenticationFailed):
                return None

        return None
