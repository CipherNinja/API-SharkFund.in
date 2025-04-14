from django.contrib.auth.backends import ModelBackend
from cloudManager.models import CustomUser
from django.db.models import Q

class CustomAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Look up user by email or username (case-insensitive)
            user = CustomUser.objects.get(
                Q(email__iexact=username) | Q(username__iexact=username)
            )
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None
        return None