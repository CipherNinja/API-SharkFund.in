from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)  # Ensures email is unique
    address = models.TextField(null=True, blank=True)
    mobile_number = models.CharField(max_length=15, null=True, blank=True)

    def __str__(self):
        return self.username
